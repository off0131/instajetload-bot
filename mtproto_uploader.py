"""
High-Speed MTProto Engine for @instajetloadbot
Bypasses the 50MB Telegram Bot API limit and delivers media up to 2,000 MB (2 GB)
directly inside Telegram chat with parallel chunks and native video streaming.
"""

import os
import asyncio
import logging
from typing import Optional, Callable
from telethon import TelegramClient
from telethon.tl.types import (
    DocumentAttributeVideo,
    DocumentAttributeAudio,
    DocumentAttributeFilename,
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
            logger.info("⚡ MTProto 2GB Uploader Engine started successfully.")
            return _client
        except Exception as e:
            logger.error(f"Failed to start MTProto client: {e}", exc_info=True)
            return None


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
    Sends video up to 2,000 MB (2 GB) directly to chat via MTProto with streaming enabled.
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

        attrs = [
            DocumentAttributeVideo(
                duration=dur,
                w=w,
                h=h,
                supports_streaming=True,
            )
        ]

        thumb_path = thumb if (thumb and os.path.exists(thumb)) else None

        await client.send_file(
            entity=chat_id,
            file=file_path,
            caption=caption,
            thumb=thumb_path,
            force_document=False,
            supports_streaming=True,
            mime_type="video/mp4",
            attributes=attrs,
            progress_callback=progress_callback,
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
    Sends audio up to 2,000 MB (2 GB) directly to chat via MTProto.
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

        await client.send_file(
            entity=chat_id,
            file=file_path,
            caption=caption,
            attributes=attrs,
            progress_callback=progress_callback,
        )
        return True
    except Exception as e:
        logger.error(f"MTProto audio upload error: {e}", exc_info=True)
        return False
