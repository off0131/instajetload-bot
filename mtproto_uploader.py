"""
High-Speed MTProto Engine for @instajetloadbot
Bypasses the 50MB Telegram Bot API limit and delivers media up to 2,000 MB (2 GB)
directly inside Telegram chat with parallel multi-part chunks and native video streaming.
FastTelethon parallel connection architecture ensures maximum throughput.
"""

import os
import math
import inspect
import asyncio
import logging
from typing import Optional, Callable, List, Tuple, Union
from telethon import TelegramClient, helpers, utils
from telethon.tl.types import (
    DocumentAttributeVideo,
    DocumentAttributeAudio,
    DocumentAttributeFilename,
    InputFile,
    InputFileBig,
    TypeInputFile,
)
from telethon.tl.functions.upload import SaveBigFilePartRequest, SaveFilePartRequest
from telethon.network import MTProtoSender
from telethon.tl.alltlobjects import LAYER
from telethon.tl.functions import InvokeWithLayerRequest
from telethon.tl.functions.auth import (
    ExportAuthorizationRequest,
    ImportAuthorizationRequest,
)

logger = logging.getLogger("instajet.mtproto")

API_ID = int(os.environ.get("TELEGRAM_API_ID", 2040))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "b18441a1ff607e10a989891a5462e627")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8887835224:AAGxM5MW1h5FhuSvIsFMI2M1GwgAX5fLNQM")

SESSION_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "session")
os.makedirs(SESSION_DIR, exist_ok=True)
SESSION_FILE = os.path.join(SESSION_DIR, "instajet_mtproto")

_client: Optional[TelegramClient] = None
_client_lock = asyncio.Lock()


async def get_mtproto_client() -> Optional[TelegramClient]:
    """Retrieve or initialize the singleton MTProto TelegramClient."""
    global _client
    async with _client_lock:
        if _client is not None and _client.is_connected():
            return _client

        try:
            client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
            await client.connect()
            if not await client.is_user_authorized():
                await client.start(bot_token=BOT_TOKEN)
            _client = client
            _client.parse_mode = "html"
            logger.info("⚡ MTProto 2GB Uploader Engine started successfully.")
            return _client
        except Exception as e:
            logger.error(f"Failed to start MTProto client: {e}", exc_info=True)
            return None


class UploadSender:
    """Handles sending individual chunk parts over an MTProto sender connection."""

    def __init__(
        self,
        client: TelegramClient,
        sender: MTProtoSender,
        file_id: int,
        part_count: int,
        big: bool,
        index: int,
        stride: int,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self.client = client
        self.sender = sender
        self.file_id = file_id
        self.part_count = part_count
        self.big = big
        self.part_index = index
        self.stride = stride
        self.loop = loop
        self.previous: Optional[asyncio.Task] = None

    async def next(self, data: bytes) -> None:
        if self.previous:
            await self.previous
        idx = self.part_index
        self.part_index += self.stride
        self.previous = self.loop.create_task(self._send_chunk(idx, data))

    async def _send_chunk(self, part_index: int, data: bytes) -> None:
        if self.big:
            req = SaveBigFilePartRequest(self.file_id, part_index, self.part_count, data)
        else:
            req = SaveFilePartRequest(self.file_id, part_index, data)
        await self.client._call(self.sender, req)

    async def disconnect(self) -> None:
        if self.previous:
            await self.previous
        await self.sender.disconnect()


class ParallelTransferrer:
    """
    Orchestrates high-speed parallel file transfers across multiple MTProto connections.
    """

    def __init__(self, client: TelegramClient, dc_id: Optional[int] = None) -> None:
        self.client = client
        self.loop = self.client.loop
        self.dc_id = dc_id or self.client.session.dc_id
        self.auth_key = (
            None
            if dc_id and self.client.session.dc_id != dc_id
            else self.client.session.auth_key
        )
        self.senders: Optional[List[UploadSender]] = None
        self.upload_ticker = 0

    async def _cleanup(self) -> None:
        if self.senders:
            results = await asyncio.gather(
                *[sender.disconnect() for sender in self.senders],
                return_exceptions=True,
            )
            self.senders = None
            for r in results:
                if isinstance(r, Exception):
                    raise r

    @staticmethod
    def _get_connection_count(
        file_size: int, max_count: int = 8, full_size: int = 100 * 1024 * 1024
    ) -> int:
        if file_size > full_size:
            return max_count
        count = math.ceil((file_size / full_size) * max_count)
        return max(2, min(count, max_count))

    async def _create_sender(self) -> MTProtoSender:
        dc = await self.client._get_dc(self.dc_id)
        sender = MTProtoSender(self.auth_key, loggers=self.client._log)
        await sender.connect(
            self.client._connection(
                dc.ip_address,
                dc.port,
                dc.id,
                loggers=self.client._log,
                proxy=self.client._proxy,
                local_addr=getattr(self.client, "_local_addr", None),
            )
        )
        if not self.auth_key:
            auth = await self.client(ExportAuthorizationRequest(self.dc_id))
            from copy import copy
            init_req = copy(self.client._init_request)
            init_req.query = ImportAuthorizationRequest(
                id=auth.id, bytes=auth.bytes
            )
            req = InvokeWithLayerRequest(LAYER, init_req)
            await sender.send(req)
            self.auth_key = sender.auth_key
        return sender

    async def _create_upload_sender(
        self, file_id: int, part_count: int, big: bool, index: int, stride: int
    ) -> UploadSender:
        return UploadSender(
            self.client,
            await self._create_sender(),
            file_id,
            part_count,
            big,
            index,
            stride,
            loop=self.loop,
        )

    async def _init_upload(
        self, connections: int, file_id: int, part_count: int, big: bool
    ) -> None:
        self.senders = [
            await self._create_upload_sender(file_id, part_count, big, 0, connections),
            *await asyncio.gather(
                *[
                    self._create_upload_sender(file_id, part_count, big, i, connections)
                    for i in range(1, connections)
                ]
            ),
        ]

    async def init_upload(
        self,
        file_id: int,
        file_size: int,
        part_size_kb: Optional[float] = None,
        connection_count: Optional[int] = None,
    ) -> Tuple[int, int, bool]:
        connection_count = connection_count or self._get_connection_count(file_size)
        part_size = int((part_size_kb or utils.get_appropriated_part_size(file_size)) * 1024)
        part_count = (file_size + part_size - 1) // part_size
        is_large = file_size > 10 * 1024 * 1024
        await self._init_upload(connection_count, file_id, part_count, is_large)
        return part_size, part_count, is_large

    async def upload(self, part: bytes) -> None:
        await self.senders[self.upload_ticker].next(part)
        self.upload_ticker = (self.upload_ticker + 1) % len(self.senders)

    async def finish_upload(self) -> None:
        await self._cleanup()


async def fast_upload_file(
    client: TelegramClient,
    file_path: str,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> Union[TypeInputFile, str]:
    """
    High-speed parallel multi-part file upload using FastTelethon architecture.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    file_size = os.path.getsize(file_path)
    file_name = os.path.basename(file_path)

    # For small files (<= 10 MB), standard client.upload_file is already instantaneous
    if file_size <= 10 * 1024 * 1024:
        return await client.upload_file(
            file_path,
            progress_callback=progress_callback,
        )

    file_id = helpers.generate_random_long()
    part_size = 512 * 1024  # 512 KB
    part_count = (file_size + part_size - 1) // part_size

    uploader = ParallelTransferrer(client)
    try:
        conn_count = 16 if file_size > 50 * 1024 * 1024 else 8
        await uploader.init_upload(file_id, file_size, part_size_kb=512, connection_count=conn_count)
        bytes_sent = 0
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(part_size)
                if not chunk:
                    break
                await uploader.upload(chunk)
                bytes_sent += len(chunk)
                if progress_callback:
                    try:
                        res = progress_callback(bytes_sent, file_size)
                        if inspect.isawaitable(res):
                            await res
                    except Exception:
                        pass
        await uploader.finish_upload()
        return InputFileBig(file_id, part_count, file_name)
    except Exception as e:
        logger.warning(f"Parallel MTProto transfer encountered error ({e}), falling back to standard upload")
        try:
            await uploader.finish_upload()
        except Exception:
            pass
        return await client.upload_file(file_path, progress_callback=progress_callback)


async def send_mtproto_video(
    chat_id: int,
    file_path: str,
    caption: str = "",
    duration: int = 0,
    width: int = 0,
    height: int = 0,
    thumb: Optional[str] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> bool:
    """
    Sends video up to 2,000 MB (2 GB) directly to chat via high-speed MTProto with streaming enabled.
    """
    client = await get_mtproto_client()
    if not client:
        logger.error("MTProto client not available")
        return False

    try:
        filename = os.path.basename(file_path)
        dur = int(round(float(duration or 0)))
        w = int(round(float(width or 0)))
        h = int(round(float(height or 0)))

        # Auto-resolve dimensions if missing/zero
        if dur <= 0 or w <= 0 or h <= 0:
            try:
                from downloader import get_media_dimensions, probe_with_ffmpeg
                w_chk, h_chk, dur_chk = get_media_dimensions(file_path)
                dur = dur or dur_chk or 0
                w = w or w_chk or 1280
                h = h or h_chk or 720
                if dur <= 0:
                    _, _, dur_ff = probe_with_ffmpeg(file_path)
                    dur = dur or dur_ff or 0
            except Exception:
                dur = dur or 0
                w = w or 1280
                h = h or 720

        attrs = [
            DocumentAttributeVideo(
                duration=dur,
                w=w,
                h=h,
                supports_streaming=True,
            ),
        ]

        thumb_path = thumb if (thumb and os.path.exists(thumb)) else None
        if not thumb_path:
            candidate = os.path.join(os.path.dirname(file_path), f"{os.path.splitext(filename)[0]}_thumb.jpg")
            if os.path.exists(candidate) and os.path.getsize(candidate) > 0:
                thumb_path = candidate

        # Upload file at high speed via parallel MTProto chunk pipeline
        file_to_send: Union[TypeInputFile, str] = file_path
        try:
            logger.info(f"Starting parallel high-speed MTProto upload for {filename} ({os.path.getsize(file_path)} bytes)")
            file_to_send = await fast_upload_file(
                client=client,
                file_path=file_path,
                progress_callback=progress_callback,
            )
        except Exception as e_upload:
            logger.warning(f"Parallel upload failed ({e_upload}), using standard path send: {e_upload}")
            file_to_send = file_path

        await client.send_file(
            entity=chat_id,
            file=file_to_send,
            caption=caption,
            thumb=thumb_path,
            force_document=False,
            supports_streaming=True,
            mime_type="video/mp4",
            attributes=attrs,
            parse_mode="html",
            progress_callback=progress_callback if file_to_send == file_path else None,
        )
        return True
    except Exception as e:
        logger.error(f"MTProto video upload error: {e}", exc_info=True)
        return False


async def send_mtproto_audio(
    chat_id: int,
    file_path: str,
    caption: str = "",
    title: str = "Audio",
    performer: str = "YouTube",
    duration: int = 0,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> bool:
    """
    Sends audio up to 2,000 MB (2 GB) directly to chat via high-speed MTProto.
    """
    client = await get_mtproto_client()
    if not client:
        logger.error("MTProto client not available")
        return False

    try:
        filename = os.path.basename(file_path)
        dur = int(round(float(duration or 0)))

        attrs = [
            DocumentAttributeAudio(
                duration=dur,
                title=title,
                performer=performer,
            ),
            DocumentAttributeFilename(file_name=filename),
        ]

        # Upload file at high speed via parallel MTProto chunk pipeline
        file_to_send: Union[TypeInputFile, str] = file_path
        try:
            logger.info(f"Starting parallel high-speed MTProto upload for audio {filename} ({os.path.getsize(file_path)} bytes)")
            file_to_send = await fast_upload_file(
                client=client,
                file_path=file_path,
                progress_callback=progress_callback,
            )
        except Exception as e_upload:
            logger.warning(f"Parallel upload failed ({e_upload}), using standard path send: {e_upload}")
            file_to_send = file_path

        await client.send_file(
            entity=chat_id,
            file=file_to_send,
            caption=caption,
            attributes=attrs,
            parse_mode="html",
            progress_callback=progress_callback if file_to_send == file_path else None,
        )
        return True
    except Exception as e:
        logger.error(f"MTProto audio upload error: {e}", exc_info=True)
        return False
