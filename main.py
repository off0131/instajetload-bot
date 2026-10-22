import asyncio
import logging
import os
import re
import html
import shutil
import secrets
import time
import urllib.parse
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

import aiohttp
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile,
    InputMediaPhoto,
    InputMediaVideo,
    BotCommand,
    BotCommandScopeDefault,
    BotCommandScopeChat,
)
from aiogram.enums import ChatAction, ParseMode
from aiogram.client.default import DefaultBotProperties

from database import (
    init_db,
    add_or_update_user,
    get_user_lang,
    set_user_lang,
    get_cached,
    save_cache,
    log_download,
    get_stats,
    get_all_user_ids,
    clear_cache_db,
)
from locales import LANGUAGES, get_text
from downloader import (
    download_instagram_media,
    cleanup_task_dir,
    extract_shortcode,
    detect_platform,
    get_youtube_info,
    download_youtube,
    download_spotify,
    download_spotify_album,
    get_spotify_info,
    download_generic,
    get_youtube_direct_cdn_url,
    get_media_dimensions,
    probe_with_ffmpeg,
)
from mtproto_uploader import send_mtproto_video, send_mtproto_audio

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("توکن ربات در فایل .env تعریف نشده است.")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("InstaJetLoadBot")

# In-memory recent error & diagnostics ring buffer (keeps last 50 logs)
from collections import deque
RECENT_LOGS = deque(maxlen=50)

class MemoryLogHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
            RECENT_LOGS.append(msg)
        except Exception:
            pass

mem_handler = MemoryLogHandler()
mem_handler.setLevel(logging.INFO)
mem_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(mem_handler)
logging.getLogger().addHandler(mem_handler)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# Memory & concurrency guard for Render 512MB RAM limit
DOWNLOAD_SEMAPHORE = asyncio.Semaphore(2)

ADMIN_IDS = [
    int(x.strip()) for x in os.getenv("ADMIN_IDS", "94812102,110268093").split(",") if x.strip().isdigit()
]

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def get_language_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="🇮🇷 فارسی", callback_data="lang:fa"),
            InlineKeyboardButton(text="🇺🇸 English", callback_data="lang:en"),
        ],
        [
            InlineKeyboardButton(text="🇸🇦 العربية", callback_data="lang:ar"),
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"),
        ],
        [
            InlineKeyboardButton(text="🇨🇳 中文", callback_data="lang:zh"),
            InlineKeyboardButton(text="🇩🇪 Deutsch", callback_data="lang:de"),
        ],
        [
            InlineKeyboardButton(text="🇪🇸 Español", callback_data="lang:es"),
            InlineKeyboardButton(text="🇫🇷 Français", callback_data="lang:fr"),
        ],
        [
            InlineKeyboardButton(text="🇹🇷 Türkçe", callback_data="lang:tr"),
            InlineKeyboardButton(text="🇮🇳 हिन्दी", callback_data="lang:hi"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_main_keyboard(lang: str = "fa") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=get_text("btn_tips", lang), callback_data="tips"),
                InlineKeyboardButton(text=get_text("btn_change_lang", lang), callback_data="change_lang"),
            ],
            [
                InlineKeyboardButton(text=get_text("btn_share", lang), switch_inline_query=get_text("share_text", lang)),
            ]
        ]
    )

def get_admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 آمار تفصیلی و کاربران", callback_data="admin:stats"),
                InlineKeyboardButton(text="📢 ارسال پیام همگانی", callback_data="admin:broadcast_info"),
            ],
            [
                InlineKeyboardButton(text="🧹 پاکسازی کش دیتابیس", callback_data="admin:clear_cache"),
                InlineKeyboardButton(text="⚡️ تست سرعت و سلامت سرور", callback_data="admin:server_ping"),
            ],
            [
                InlineKeyboardButton(text="❌ بستن پنل مدیریت", callback_data="admin:close"),
            ]
        ]
    )

@dp.message(CommandStart())
async def handle_start(message: types.Message):
    user = message.from_user
    user_id = user.id if user else 0
    name = user.first_name if user else "Friend"

    detected_lang = "en"
    if user and user.language_code:
        code = user.language_code.lower()
        for k in LANGUAGES:
            if code.startswith(k):
                detected_lang = k
                break

    is_new = False
    if user:
        is_new = await add_or_update_user(
            user.id,
            user.username or "",
            user.first_name or "",
            default_lang=detected_lang
        )

    # If it is a new user, present the language selector first!
    if is_new:
        welcome_intro = (
            f"👋 Hello {name}! Welcome to <b>InstaJetLoad</b>\n"
            f"سلام {name} عزیز! به ربات <b>InstaJetLoad</b> خوش آمدید\n\n"
            "🌐 <b>Please choose your language / لطفاً زبان خود را انتخاب کنید:</b>"
        )
        await message.answer(welcome_intro, reply_markup=get_language_keyboard())
        return

    lang = await get_user_lang(user_id)
    welcome_text = get_text("welcome", lang, name=name)
    await message.answer(welcome_text, reply_markup=get_main_keyboard(lang))

@dp.message(Command("language", "lang"))
async def handle_cmd_language(message: types.Message):
    user_id = message.from_user.id if message.from_user else 0
    lang = await get_user_lang(user_id)
    await message.answer(get_text("choose_lang", lang), reply_markup=get_language_keyboard())

@dp.callback_query(F.data == "change_lang")
async def cb_change_language(callback: types.CallbackQuery):
    user_id = callback.from_user.id if callback.from_user else 0
    lang = await get_user_lang(user_id)
    await callback.message.answer(get_text("choose_lang", lang), reply_markup=get_language_keyboard())
    await callback.answer()

@dp.callback_query(F.data.startswith("lang:"))
async def cb_select_language(callback: types.CallbackQuery):
    target_lang = callback.data.split(":")[1]
    if target_lang not in LANGUAGES:
        target_lang = "en"

    user_id = callback.from_user.id if callback.from_user else 0
    name = callback.from_user.first_name if callback.from_user else "Friend"
    await set_user_lang(user_id, target_lang)

    alert_text = get_text("lang_updated", target_lang)
    await callback.answer(alert_text, show_alert=True)

    welcome_text = get_text("welcome", target_lang, name=name)
    await callback.message.answer(welcome_text, reply_markup=get_main_keyboard(target_lang))

@dp.callback_query(F.data == "tips")
async def cb_tips(callback: types.CallbackQuery):
    user_id = callback.from_user.id if callback.from_user else 0
    lang = await get_user_lang(user_id)
    await callback.message.answer(get_text("tips_content", lang))
    await callback.answer()

@dp.message(Command("admin"))
async def handle_cmd_admin(message: types.Message):
    user_id = message.from_user.id if message.from_user else 0
    if not is_admin(user_id):
        return  # Only accessible to admins

    text = (
        "👑 <b>پنل اختصاصی مدیریت ربات InstaJetLoad:</b>\n\n"
        "به پنل کنترل ربات خوش آمدید! لطفاً عملیات مورد نظر را انتخاب نمایید: ⚡️"
    )
    await message.answer(text, reply_markup=get_admin_keyboard())

@dp.message(Command("stats"))
async def handle_cmd_stats(message: types.Message):
    user_id = message.from_user.id if message.from_user else 0
    if not is_admin(user_id):
        return  # Completely hidden from regular users

    stats = await get_stats()
    text = (
        "<b>📊 آمار و تحلیل عملکرد ربات (پنل ادمین):</b> 👑\n\n"
        f"👥 کل کاربران ثبت‌شده: <b>{stats['users']}</b> نفر 🔥\n"
        f"🆕 کاربران ورودی امروز: <b>{stats.get('users_today', 0)}</b> نفر ✨\n"
        f"📥 کل دانلودهای موفق: <b>{stats['downloads']}</b> بار ⚡️\n"
        f"🎯 دانلودهای ثبت‌شده امروز: <b>{stats.get('downloads_today', 0)}</b> بار 🚀\n"
        f"💾 فایل‌های ذخیره در کش سرور: <b>{stats['cached']}</b> عدد 📦\n\n"
        "🟢 وضعیت سرور ابری: <b>Online & Active 24/7 (Render)</b>"
    )
    await message.answer(text)

@dp.message(Command("broadcast"))
async def handle_cmd_broadcast(message: types.Message):
    user_id = message.from_user.id if message.from_user else 0
    if not is_admin(user_id):
        return

    text_to_send = message.text.replace("/broadcast", "", 1).strip()
    if not text_to_send:
        await message.answer(
            "📢 <b>راهنمای ارسال پیام همگانی:</b>\n\n"
            "متن پیام خود را پس از دستور با یک فاصله بنویسید:\n"
            "<code>/broadcast متن پیام شما به تمام کاربران...</code>"
        )
        return

    status_msg = await message.answer("⏳ در حال آغاز ارسال پیام همگانی به کاربران...")
    user_ids = await get_all_user_ids()
    success = 0
    failed = 0

    for uid in user_ids:
        try:
            await bot.send_message(chat_id=uid, text=text_to_send)
            success += 1
            await asyncio.sleep(0.04)  # Anti-flood rate limit
        except Exception:
            failed += 1

    await status_msg.edit_text(
        f"✅ <b>گزارش ارسال پیام همگانی به پایان رسید:</b>\n\n"
        f"▫️ دریافت موفق: <b>{success}</b> کاربر\n"
        f"▫️ ناموفق (بلاک ربات یا خطای اکانت): <b>{failed}</b> کاربر"
    )

@dp.callback_query(F.data.startswith("admin:"))
async def handle_admin_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id if callback.from_user else 0
    if not is_admin(user_id):
        await callback.answer("⛔️ دسترسی غیرمجاز!", show_alert=True)
        return

    action = callback.data.split(":")[1]

    if action == "close":
        await callback.message.delete()
        await callback.answer("پنل مدیریت بسته شد.")
        return

    if action == "main":
        text = (
            "👑 <b>پنل اختصاصی مدیریت ربات InstaJetLoad:</b>\n\n"
            "به پنل کنترل ربات خوش آمدید! لطفاً عملیات مورد نظر را انتخاب نمایید: ⚡️"
        )
        await callback.message.edit_text(text, reply_markup=get_admin_keyboard())
        await callback.answer()
        return

    if action == "stats":
        stats = await get_stats()
        text = (
            "<b>📊 آمار و تحلیل عملکرد ربات (پنل ادمین):</b> 👑\n\n"
            f"👥 کل کاربران ثبت‌شده: <b>{stats['users']}</b> نفر 🔥\n"
            f"🆕 کاربران ورودی امروز: <b>{stats.get('users_today', 0)}</b> نفر ✨\n"
            f"📥 کل دانلودهای موفق: <b>{stats['downloads']}</b> بار ⚡️\n"
            f"🎯 دانلودهای ثبت‌شده امروز: <b>{stats.get('downloads_today', 0)}</b> بار 🚀\n"
            f"💾 فایل‌های ذخیره در کش سرور: <b>{stats['cached']}</b> عدد 📦\n\n"
            "🟢 وضعیت سرور ابری: <b>Online & Active 24/7 (Render)</b>"
        )
        back_kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔙 بازگشت به منوی ادمین", callback_data="admin:main")]]
        )
        await callback.message.edit_text(text, reply_markup=back_kb)
        await callback.answer()
        return

    if action == "broadcast_info":
        text = (
            "📢 <b>ارسال پیام به تمام کاربران:</b>\n\n"
            "برای ارسال اطلاعیه، پیام یا تبلیغ به تمامی اعضای ربات، کافیست دستور زیر را ارسال کنید:\n\n"
            "<code>/broadcast متن پیام شما در اینجا</code>"
        )
        back_kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔙 بازگشت به منوی ادمین", callback_data="admin:main")]]
        )
        await callback.message.edit_text(text, reply_markup=back_kb)
        await callback.answer()
        return

    if action == "clear_cache":
        deleted = await clear_cache_db()
        await callback.answer(f"🧹 کش دیتابیس با موفقیت خالی شد ({deleted} فایل کش پاک شد).", show_alert=True)
        return

    if action == "server_ping":
        await callback.answer("🟢 سرور ابری Render کاملاً فعال و سرعت اتصال در حداکثر توان است! ⚡️🏎", show_alert=True)
        return

GENERAL_URL_PATTERN = re.compile(
    r"(?:https?:\/\/|www\.)\S+|(?:\b(?:instagram|instagr|youtube|youtu|spotify|soundcloud|tiktok|twitter|x|pinterest|pin)\.(?:com|be|am|it|link|app)\/\S+)",
    re.IGNORECASE
)

def format_caption(caption: str, max_length: int = 850) -> str:
    bot_tag = "\n\n🆔 @instajetloadbot"
    if not caption or not caption.strip():
        return "🆔 @instajetloadbot"

    clean = caption.strip()
    if len(clean) > max_length:
        clean = clean[:max_length].rstrip() + "..."

    escaped = html.escape(clean)
    # Ensure total HTML caption length stays strictly below Telegram limit (1024 chars)
    while len(f"<blockquote expandable><code>{escaped}</code></blockquote>{bot_tag}") > 1020 and len(clean) > 50:
        clean = clean[:-20].rstrip() + "..."
        escaped = html.escape(clean)

    return f"<blockquote expandable><code>{escaped}</code></blockquote>{bot_tag}"

def plain_caption(caption: str, max_length: int = 850) -> str:
    bot_tag = "\n\n🆔 @instajetloadbot"
    if not caption or not caption.strip():
        return "🆔 @instajetloadbot"
    clean = caption.strip()
    if len(clean) > max_length:
        clean = clean[:max_length].rstrip() + "..."
    return f"{clean}{bot_tag}"

truncate_caption = format_caption

def sanitize_media_kwargs(kwargs: dict) -> dict:
    cleaned = dict(kwargs)
    for int_key in ("duration", "width", "height"):
        if int_key in cleaned:
            val = cleaned[int_key]
            if val is not None:
                try:
                    num = int(round(float(val)))
                    if num > 0:
                        cleaned[int_key] = num
                    else:
                        cleaned.pop(int_key, None)
                except Exception:
                    cleaned.pop(int_key, None)
            else:
                cleaned.pop(int_key, None)
    return cleaned

@asynccontextmanager
async def keep_chat_action(bot_instance: Bot, chat_id: int, action: str = ChatAction.UPLOAD_VIDEO, interval: float = 4.0):
    """Continuously refreshes chat action (e.g. 'sending video...') in Telegram status bar until task finishes."""
    stop_event = asyncio.Event()

    async def _action_loop():
        while not stop_event.is_set():
            try:
                await bot_instance.send_chat_action(chat_id, action)
            except Exception:
                pass
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass

    task = asyncio.create_task(_action_loop())
    try:
        yield
    finally:
        stop_event.set()
        try:
            await task
        except Exception:
            pass

async def safe_reply_video(message_or_cb, video, caption: str, **kwargs):
    """Replies with video, safely falling back to plain caption or no caption if entity parsing fails."""
    kwargs = sanitize_media_kwargs(kwargs)
    try:
        return await message_or_cb.reply_video(video=video, caption=caption, parse_mode=ParseMode.HTML, **kwargs)
    except Exception as e:
        logger.warning(f"Video HTML caption failed ({e}), falling back to plain caption...")
        try:
            return await message_or_cb.reply_video(video=video, caption=plain_caption(caption), parse_mode=None, **kwargs)
        except Exception as e2:
            logger.warning(f"Video plain caption failed ({e2}), sending without caption...")
            return await message_or_cb.reply_video(video=video, caption="🆔 @instajetloadbot", parse_mode=None, **kwargs)

async def safe_reply_audio(message_or_cb, audio, caption: str, **kwargs):
    """Replies with audio, safely falling back to plain caption if entity parsing fails."""
    kwargs = sanitize_media_kwargs(kwargs)
    try:
        return await message_or_cb.reply_audio(audio=audio, caption=caption, parse_mode=ParseMode.HTML, **kwargs)
    except Exception as e:
        logger.warning(f"Audio HTML caption failed ({e}), falling back to plain caption...")
        try:
            return await message_or_cb.reply_audio(audio=audio, caption=plain_caption(caption), parse_mode=None, **kwargs)
        except Exception as e2:
            logger.warning(f"Audio plain caption failed ({e2}), sending without caption...")
            return await message_or_cb.reply_audio(audio=audio, caption="🆔 @instajetloadbot", parse_mode=None, **kwargs)

async def safe_reply_photo(message_or_cb, photo, caption: str, **kwargs):
    """Replies with photo, safely falling back to plain caption if entity parsing fails."""
    try:
        return await message_or_cb.reply_photo(photo=photo, caption=caption, parse_mode=ParseMode.HTML, **kwargs)
    except Exception as e:
        logger.warning(f"Photo HTML caption failed ({e}), falling back to plain caption...")
        try:
            return await message_or_cb.reply_photo(photo=photo, caption=plain_caption(caption), parse_mode=None, **kwargs)
        except Exception as e2:
            logger.warning(f"Photo plain caption failed ({e2}), sending without caption...")
            return await message_or_cb.reply_photo(photo=photo, caption="🆔 @instajetloadbot", parse_mode=None, **kwargs)

async def process_instagram_url(message: types.Message, url: str):
    user = message.from_user
    user_id = user.id if user else 0
    lang = await get_user_lang(user_id)
    shortcode = extract_shortcode(url)

    status_msg = await message.reply(get_text("downloading_general", lang))

    async with keep_chat_action(bot, message.chat.id, ChatAction.UPLOAD_VIDEO):
        # 1. Check database cache
        if shortcode:
            cached = await get_cached(shortcode)
            if cached:
                media_items = cached.get("file_ids", [])
                has_bad_video = any(
                    i.get("type") == "video" and (not i.get("duration") or i.get("duration") <= 2)
                    for i in media_items
                )
                if has_bad_video:
                    logger.info(f"Cached video for {shortcode} is corrupt/short, re-downloading freshly.")
                else:
                    try:
                        caption_text = truncate_caption(cached.get("caption", ""))

                        if len(media_items) == 1:
                            item = media_items[0]
                            if item["type"] == "video":
                                await safe_reply_video(
                                    message,
                                    video=item["file_id"],
                                    caption=caption_text,
                                    width=item.get("width"),
                                    height=item.get("height"),
                                    duration=item.get("duration"),
                                    supports_streaming=True
                                )
                            else:
                                await safe_reply_photo(message, photo=item["file_id"], caption=caption_text)
                        elif len(media_items) > 1:
                            media_group = []
                            for idx, itm in enumerate(media_items[:10]):
                                c = caption_text if idx == 0 else None
                                if itm["type"] == "video":
                                    media_group.append(InputMediaVideo(
                                        media=itm["file_id"],
                                        caption=c,
                                        width=itm.get("width"),
                                        height=itm.get("height"),
                                        duration=int(round(float(itm.get("duration")))) if itm.get("duration") else None,
                                        supports_streaming=True
                                    ))
                                else:
                                    media_group.append(InputMediaPhoto(media=itm["file_id"], caption=c))
                            try:
                                await message.reply_media_group(media=media_group)
                            except Exception:
                                # Retry media group without caption if entity parse error
                                for m in media_group:
                                    m.caption = None
                                await message.reply_media_group(media=media_group)

                        await log_download(user.id if user else 0, shortcode)
                        await status_msg.delete()
                        return
                    except Exception as e:
                        logger.warning(f"Cache delivery failed, downloading freshly: {e}")

        # 2. Download freshly
        task_dir = None
        try:
            async with DOWNLOAD_SEMAPHORE:
                result = await download_instagram_media(url)
            task_dir = result.get("task_dir")
            sc = result.get("shortcode") or shortcode or "unknown"
            caption = result.get("caption", "")
            formatted_caption = truncate_caption(caption)
            items = result.get("items", [])

            if not items:
                await status_msg.edit_text("❌ محتوایی برای دانلود در این لینک یافت نشد.")
                return

            saved_file_ids = []

            if len(items) == 1:
                item = items[0]
                file_input = FSInputFile(item["path"])
                if item["type"] == "video":
                    sent = await safe_reply_video(
                        message,
                        video=file_input,
                        caption=formatted_caption,
                        width=item.get("width"),
                        height=item.get("height"),
                        duration=item.get("duration"),
                        supports_streaming=True
                    )
                    if sent and sent.video:
                        saved_file_ids.append({
                            "type": "video",
                            "file_id": sent.video.file_id,
                            "width": item.get("width"),
                            "height": item.get("height"),
                            "duration": item.get("duration")
                        })
                elif item["type"] == "photo":
                    sent = await safe_reply_photo(message, photo=file_input, caption=formatted_caption)
                    if sent and sent.photo:
                        saved_file_ids.append({"type": "photo", "file_id": sent.photo[-1].file_id})
                else:
                    sent = await message.reply_document(document=file_input, caption=plain_caption(formatted_caption))
                    if sent and sent.document:
                        saved_file_ids.append({"type": "document", "file_id": sent.document.file_id})
            else:
                # Multi-slide album / Carousel
                batches = [items[i:i + 10] for i in range(0, len(items), 10)]
                for b_idx, batch in enumerate(batches):
                    media_group = []
                    for idx, itm in enumerate(batch):
                        f_input = FSInputFile(itm["path"])
                        c = formatted_caption if (b_idx == 0 and idx == 0) else None
                        if itm["type"] == "video":
                            media_group.append(InputMediaVideo(
                                media=f_input,
                                caption=c,
                                width=itm.get("width"),
                                height=itm.get("height"),
                                duration=int(round(float(itm.get("duration")))) if itm.get("duration") else None,
                                supports_streaming=True
                            ))
                        else:
                            media_group.append(InputMediaPhoto(media=f_input, caption=c))

                    sent_msgs = await message.reply_media_group(media=media_group)
                    for idx, s_msg in enumerate(sent_msgs):
                        orig_item = batch[idx] if idx < len(batch) else {}
                        if s_msg.video:
                            saved_file_ids.append({
                                "type": "video",
                                "file_id": s_msg.video.file_id,
                                "width": orig_item.get("width"),
                                "height": orig_item.get("height"),
                                "duration": orig_item.get("duration")
                            })
                        elif s_msg.photo:
                            saved_file_ids.append({"type": "photo", "file_id": s_msg.photo[-1].file_id})

            if saved_file_ids and sc:
                await save_cache(sc, "album" if len(items) > 1 else items[0]["type"], saved_file_ids, caption)

            if user:
                await log_download(user.id, sc)

            await status_msg.delete()

        except Exception as e:
            logger.error(f"Download error: {e}", exc_info=True)
            err_msg = str(e)
            if "private" in err_msg.lower() or "followers" in err_msg.lower():
                text = get_text("err_private", lang)
            else:
                text = get_text("err_general", lang)
            await status_msg.edit_text(text)
        finally:
            if task_dir:
                cleanup_task_dir(task_dir)

async def process_youtube_url(message: types.Message, url: str):
    user_id = message.from_user.id if message.from_user else 0
    lang = await get_user_lang(user_id)
    status_msg = await message.reply(get_text("yt_fetching_info", lang))
    async with keep_chat_action(bot, message.chat.id, ChatAction.TYPING):
        try:
            info = await get_youtube_info(url)
            video_id = info["id"]
            title = info.get("title", "YouTube Video")
            duration = info.get("duration", 0)
            qualities_data = info.get("qualities_data") or {}
            v_quals = qualities_data.get("video_qualities") or []

            if (not duration or not any("·" in q.get("label", "") for q in v_quals)) and video_id:
                try:
                    from downloader import fetch_youtube_web_info
                    w_info = fetch_youtube_web_info(video_id)
                    if w_info.get("duration"):
                        duration = w_info["duration"]
                        info["duration"] = duration
                        qualities_data = parse_youtube_qualities({"duration": duration, "formats": []})
                        v_quals = qualities_data.get("video_qualities") or []
                    if w_info.get("title") and (not title or title == "YouTube Video"):
                        title = w_info["title"]
                    if w_info.get("channel") and (not channel or channel == "YouTube"):
                        channel = w_info["channel"]
                except Exception:
                    pass

            if duration >= 3600:
                h = duration // 3600
                m = (duration % 3600) // 60
                s = duration % 60
                dur_str = f"{h}:{m:02d}:{s:02d}"
            elif duration > 0:
                dur_str = f"{duration // 60}:{duration % 60:02d}"
            else:
                dur_str = "0:00"
            channel = info.get("channel", "YouTube")
            resolutions = info.get("resolutions") or [720, 480, 360]

            # Build inline keyboard for quality selection

            quality_buttons = []
            if v_quals:
                curr_row = []
                for q in v_quals:
                    r = q["res"]
                    lbl = q["label"]
                    curr_row.append(InlineKeyboardButton(text=lbl, callback_data=f"yt:{video_id}:{r}"))
                    if len(curr_row) == 2:
                        quality_buttons.append(curr_row)
                        curr_row = []
                if curr_row:
                    quality_buttons.append(curr_row)

                audio_high = qualities_data.get("audio_high", {})
                audio_low = qualities_data.get("audio_low", {})
                audio_row = [
                    InlineKeyboardButton(text=audio_high.get("label", "🎵 کیفیت عالی"), callback_data=f"yt:{video_id}:audio"),
                    InlineKeyboardButton(text=audio_low.get("label", "🎵 حجم کمتر"), callback_data=f"yt:{video_id}:audio_low")
                ]
                quality_buttons.append(audio_row)
            else:
                row = []
                for r in resolutions:
                    row.append(InlineKeyboardButton(text=f"🎬 {r}p", callback_data=f"yt:{video_id}:{r}"))
                    if len(row) == 2:
                        quality_buttons.append(row)
                        row = []
                if row:
                    quality_buttons.append(row)

                quality_buttons.append([
                    InlineKeyboardButton(text=get_text("yt_audio_btn", lang), callback_data=f"yt:{video_id}:audio")
                ])

            quality_buttons.append([
                InlineKeyboardButton(text=get_text("btn_cancel", lang), callback_data="yt:cancel")
            ])

            keyboard = InlineKeyboardMarkup(inline_keyboard=quality_buttons)
            text = (
                f"🎬 <b>{html.escape(title)}</b>\n\n"
                f"⏱ <code>{dur_str}</code> | 👤 <code>{html.escape(channel)}</code>\n\n"
                f"{get_text('yt_select_quality', lang)}"
            )

            thumbnail = info.get("thumbnail")
            if thumbnail:
                try:
                    await message.reply_photo(photo=thumbnail, caption=text, reply_markup=keyboard)
                    await status_msg.delete()
                    return
                except Exception:
                    pass

            await status_msg.edit_text(text, reply_markup=keyboard)
        except Exception as e:
            logger.error(f"YouTube info error: {e}", exc_info=True)
            await status_msg.edit_text(get_text("err_general", lang))

@dp.callback_query(F.data.startswith("yt:"))
async def handle_youtube_callback(callback: types.CallbackQuery):
    data = callback.data
    if data == "yt:cancel":
        await callback.message.delete()
        await callback.answer("OK")
        return

    parts = data.split(":")
    if len(parts) < 3:
        await callback.answer()
        return

    video_id = parts[1]
    quality = parts[2]
    await callback.answer()

    user_id = callback.from_user.id if callback.from_user else 0
    lang = await get_user_lang(user_id)
    is_audio = quality in ("audio", "audio_low", "mp3")
    quality_label = "صوتی (حجم کمتر)" if quality == "audio_low" else (get_text("yt_audio_btn", lang) if is_audio else f"{quality}p")
    status_msg = await callback.message.reply(get_text("yt_downloading", lang, quality=quality_label))

    chat_action = ChatAction.RECORD_VOICE if is_audio else ChatAction.UPLOAD_VIDEO
    async with keep_chat_action(bot, callback.message.chat.id, chat_action):
        cache_key = f"yt_{video_id}_{quality}"
        # 1. Check database cache
        cached = await get_cached(cache_key)
        if cached and cached.get("file_ids"):
            media_items = cached.get("file_ids", [])
            if media_items:
                try:
                    caption_text = truncate_caption(cached.get("caption", ""))
                    item = media_items[0] if isinstance(media_items[0], dict) else {"file_id": media_items[0]}
                    f_id = item.get("file_id")
                    if is_audio:
                        await safe_reply_audio(
                            callback.message,
                            audio=f_id,
                            title=item.get("title", "YouTube Audio"),
                            performer=item.get("performer", "YouTube"),
                            duration=item.get("duration", 0),
                            caption=caption_text
                        )
                    else:
                        await safe_reply_video(
                            callback.message,
                            video=f_id,
                            caption=caption_text,
                            width=item.get("width"),
                            height=item.get("height"),
                            duration=item.get("duration"),
                            supports_streaming=True
                        )
                    if callback.from_user:
                        await log_download(callback.from_user.id, cache_key)
                    await status_msg.delete()
                    return
                except Exception as e:
                    logger.warning(f"YouTube cache delivery failed, re-downloading: {e}")

        task_dir = None
        try:
            async with DOWNLOAD_SEMAPHORE:
                res = await download_youtube(video_id, quality)
            task_dir = res.get("task_dir")
            file_path = res.get("file_path")
            thumb_file = res.get("thumbnail_path")
            if not thumb_file or not os.path.exists(thumb_file):
                thumb_file = None

            file_size_mb = os.path.getsize(file_path) / (1024 * 1024) if (file_path and os.path.exists(file_path)) else 0
            formatted_caption = format_caption(f"🎵 {res.get('title', '')}" if is_audio else res.get("title", ""))

            dur_val = int(res.get("duration") or 0)
            width_val = int(res.get("width") or 0)
            height_val = int(res.get("height") or 0)
            if not is_audio and (not dur_val or dur_val <= 0 or not width_val or width_val <= 0):
                w_chk, h_chk, dur_chk = get_media_dimensions(file_path)
                dur_val = dur_chk or dur_val
                width_val = width_val or w_chk or 1280
                height_val = height_val or h_chk or 720

            if not is_audio and (not dur_val or dur_val <= 0):
                w_ff, h_ff, dur_ff = probe_with_ffmpeg(file_path)
                dur_val = dur_ff or dur_val
                width_val = width_val or w_ff or 1280
                height_val = height_val or h_ff or 720

            # Guard against delivering corrupt, truncated, or unplayable video to Telegram
            if not is_audio and (dur_val <= 0 or file_size_mb < 0.05):
                logger.error(f"Downloaded video file {file_path} is corrupt or unplayable (dur={dur_val}, size={file_size_mb:.2f}MB)")
                raise ValueError("فایل ویدیو ناقص یا آسیب‌دیده است و امکان پخش ندارد.")

            if file_size_mb > 49.5:
                # MTProto direct delivery up to 2,000 MB (2 GB)
                if file_size_mb <= 2000.0:
                    try:
                        logger.info(f"Delivering large YouTube media directly via MTProto ({file_size_mb:.1f} MB)")
                        if is_audio:
                            sent_ok = await send_mtproto_audio(
                                chat_id=callback.message.chat.id,
                                file_path=file_path,
                                caption=formatted_caption,
                                title=res.get("title", "YouTube Audio"),
                                performer=res.get("artist") or "YouTube",
                                duration=dur_val,
                            )
                        else:
                            sent_ok = await send_mtproto_video(
                                chat_id=callback.message.chat.id,
                                file_path=file_path,
                                caption=formatted_caption,
                                duration=dur_val,
                                width=width_val,
                                height=height_val,
                                thumb=thumb_file,
                            )
                        if sent_ok:
                            if callback.from_user:
                                await log_download(callback.from_user.id, cache_key)
                            await status_msg.delete()
                            return
                    except Exception as e_mt:
                        logger.error(f"MTProto direct upload failed: {e_mt}", exc_info=True)

                # Fallback to direct web link if > 2GB or if MTProto encountered an error
                token = secrets.token_urlsafe(16)
                filename = os.path.basename(file_path)
                title = res.get("title", "YouTube Media")
                q_label = "صوتی (MP3)" if is_audio else f"{quality}p"

                DIRECT_DOWNLOADS[token] = {
                    "file_path": file_path,
                    "filename": filename,
                    "title": title,
                    "size_mb": file_size_mb,
                    "quality": q_label,
                    "task_dir": task_dir,
                    "created_at": time.time(),
                }
                # Prevent the finally block from deleting task_dir while the user downloads
                task_dir = None

                server_url = get_server_base_url()
                page_url = f"{server_url}/dl/{token}"
                safe_ext = "mp3" if is_audio else "mp4"
                stream_url = f"{server_url}/file/{token}/video.{safe_ext}"

                msg_text = (
                    f"⚠️ <b>حجم فایل بیش از سقف ۲ گیگابایت است ({file_size_mb:.1f} MB)</b>\n\n"
                    f"🎬 <b>عنوان:</b> {title}\n"
                    f"📊 <b>کیفیت انتخابی:</b> {q_label}\n"
                    f"💾 <b>حجم دقیق:</b> {file_size_mb:.1f} مگابایت\n\n"
                    "🚀 <b>روش‌های دریافت فایل کامل با نهایت سرعت:</b>\n"
                    "۱️⃣ <b>کلیک روی دکمه‌های زیر</b> جهت ورود به صفحه اختصاصی دانلود و تماشای آنلاین\n"
                    "۲️⃣ <b>یا لمس و کپی کردن لینک زیر</b> (با یک‌بار لمس متن زیر کپی می‌شود) و قرار دادن آن در مرورگر Chrome یا برنامه‌های دانلود منیجر (مانند ADM یا IDM):\n\n"
                    f"🔗 <b>لینک مستقیم دانلود:</b>\n"
                    f"<code>{stream_url}</code>"
                )
                reply_markup = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=f"🌐 ورود به صفحه دانلود و تماشا ({file_size_mb:.1f} MB)", url=page_url)],
                    [InlineKeyboardButton(text="📥 دانلود مستقیم فایل (مخصوص مرورگر/ADM)", url=stream_url)]
                ])

                await status_msg.edit_text(msg_text, reply_markup=reply_markup)
                return
            try:
                if is_audio:
                    sent = await safe_reply_audio(
                        callback.message,
                        audio=FSInputFile(file_path),
                        title=res.get("title", "YouTube Audio"),
                        performer=res.get("artist") or "YouTube",
                        duration=dur_val,
                        caption=formatted_caption
                    )
                    if sent and sent.audio:
                        await save_cache(cache_key, "audio", [{
                            "file_id": sent.audio.file_id,
                            "title": res.get("title", "YouTube Audio"),
                            "performer": res.get("artist") or "YouTube",
                            "duration": dur_val
                        }], formatted_caption)
                else:
                    v_kwargs = {"supports_streaming": True}
                    if thumb_file and os.path.exists(thumb_file):
                        v_kwargs["thumbnail"] = FSInputFile(thumb_file)
                    if width_val > 0:
                        v_kwargs["width"] = width_val
                    if height_val > 0:
                        v_kwargs["height"] = height_val
                    if dur_val > 0:
                        v_kwargs["duration"] = dur_val

                    sent = await safe_reply_video(
                        callback.message,
                        video=FSInputFile(file_path),
                        caption=formatted_caption,
                        **v_kwargs
                    )
                    if sent and sent.video:
                        await save_cache(cache_key, "video", [{
                            "file_id": sent.video.file_id,
                            "width": width_val,
                            "height": height_val,
                            "duration": dur_val
                        }], formatted_caption)
            except Exception as e_bot_send:
                logger.warning(f"Standard bot delivery failed ({e_bot_send}), falling back to MTProto: {e_bot_send}")
                if is_audio:
                    mt_ok = await send_mtproto_audio(
                        chat_id=callback.message.chat.id,
                        file_path=file_path,
                        caption=formatted_caption,
                        title=res.get("title", "YouTube Audio"),
                        performer=res.get("artist") or "YouTube",
                        duration=dur_val,
                    )
                else:
                    mt_ok = await send_mtproto_video(
                        chat_id=callback.message.chat.id,
                        file_path=file_path,
                        caption=formatted_caption,
                        duration=dur_val,
                        width=width_val,
                        height=height_val,
                        thumb=thumb_file,
                    )
                if not mt_ok:
                    raise e_bot_send

            if callback.from_user:
                await log_download(callback.from_user.id, cache_key)
            await status_msg.delete()
        except Exception as e:
            logger.error(f"YouTube download error: {e}", exc_info=True)
            await status_msg.edit_text(get_text("err_general", lang))
        finally:
            if task_dir:
                cleanup_task_dir(task_dir)

async def process_spotify_url(message: types.Message, url: str):
    user_id = message.from_user.id if message.from_user else 0
    lang = await get_user_lang(user_id)
    status_msg = await message.reply(get_text("spotify_downloading", lang))

    async with keep_chat_action(bot, message.chat.id, ChatAction.RECORD_VOICE):
        # Pre-check if album or single track
        try:
            sp_info = await get_spotify_info(url)
        except Exception as e:
            logger.warning(f"Spotify info pre-fetch note: {e}")
            sp_info = None

        if sp_info and sp_info.get("type") == "album":
            tracks = sp_info.get("tracks", [])
            album_title = sp_info.get("title", "Spotify Album")
            artist = sp_info.get("artist", "")
            await status_msg.edit_text(
                f"💿 <b>{html.escape(album_title)}</b>\n👤 {html.escape(artist)}\n\n"
                f"در حال دریافت {len(tracks[:20])} قطعه از آلبوم... ⏳"
            )
            for t_idx, track in enumerate(tracks[:20], 1):
                t_id = track.get("id") or f"{track.get('title')}_{track.get('artist')}"
                cache_key = f"sp_{t_id}"
                cached = await get_cached(cache_key)
                if cached and cached.get("file_ids"):
                    c_item = cached["file_ids"][0] if isinstance(cached["file_ids"][0], dict) else {"file_id": cached["file_ids"][0]}
                    try:
                        await safe_reply_audio(
                            message,
                            audio=c_item["file_id"],
                            title=c_item.get("title", track.get("title")),
                            performer=c_item.get("artist", track.get("artist")),
                            duration=c_item.get("duration", track.get("duration", 0)),
                            caption=format_caption(f"🎵 {track.get('title', '')} ({t_idx}/{len(tracks[:20])})\n👤 {track.get('artist', '')}")
                        )
                        continue
                    except Exception:
                        pass

                t_dir = None
                try:
                    async with DOWNLOAD_SEMAPHORE:
                        t_res = await download_spotify(track)
                    t_dir = t_res.get("task_dir")
                    f_path = t_res.get("file_path")
                    if f_path and os.path.exists(f_path):
                        sent = await safe_reply_audio(
                            message,
                            audio=FSInputFile(f_path),
                            title=t_res.get("title", track.get("title")),
                            performer=t_res.get("artist", track.get("artist")),
                            duration=t_res.get("duration", 0),
                            caption=format_caption(f"🎵 {t_res.get('title', '')} ({t_idx}/{len(tracks[:20])})\n👤 {t_res.get('artist', '')}")
                        )
                        if sent and sent.audio:
                            await save_cache(cache_key, "audio", [{
                                "file_id": sent.audio.file_id,
                                "title": t_res.get("title"),
                                "artist": t_res.get("artist"),
                                "duration": int(round(float(t_res.get("duration", 0) or 0))) if t_res.get("duration") else 0
                            }], f"🎵 {t_res.get('title', '')}")
                except Exception as te:
                    logger.error(f"Error downloading album track {track.get('title')}: {te}")
                finally:
                    if t_dir:
                        cleanup_task_dir(t_dir)

            if message.from_user:
                await log_download(message.from_user.id, "spotify_album")
            await status_msg.delete()
            return

        # Single track flow
        track_match = re.search(r'track/([a-zA-Z0-9]+)', url)
        track_id = track_match.group(1) if track_match else None
        cache_key = f"sp_{track_id}" if track_id else None

        if cache_key:
            cached = await get_cached(cache_key)
            if cached and cached.get("file_ids"):
                c_item = cached["file_ids"][0] if isinstance(cached["file_ids"][0], dict) else {"file_id": cached["file_ids"][0]}
                try:
                    await safe_reply_audio(
                        message,
                        audio=c_item["file_id"],
                        title=c_item.get("title", "Spotify Track"),
                        performer=c_item.get("artist", "Spotify"),
                        duration=c_item.get("duration", 0),
                        caption=cached.get("caption", "")
                    )
                    if message.from_user:
                        await log_download(message.from_user.id, cache_key)
                    await status_msg.delete()
                    return
                except Exception as e:
                    logger.warning(f"Spotify cache delivery failed: {e}")

        task_dir = None
        try:
            async with DOWNLOAD_SEMAPHORE:
                res = await download_spotify(url)
            task_dir = res.get("task_dir")
            file_path = res.get("file_path")
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024) if file_path and os.path.exists(file_path) else 0
            caption = format_caption(f"🎵 {res.get('title', '')}\n👤 {res.get('artist', '')}")

            if file_size_mb > 49.5:
                if file_size_mb <= 2000.0:
                    try:
                        logger.info(f"Delivering large Spotify audio directly via MTProto ({file_size_mb:.1f} MB)")
                        sent_ok = await send_mtproto_audio(
                            chat_id=message.chat.id,
                            file_path=file_path,
                            caption=caption,
                            title=res.get("title", "Spotify Track"),
                            performer=res.get("artist") or "Spotify",
                            duration=res.get("duration") or 0,
                        )
                        if sent_ok:
                            if message.from_user:
                                await log_download(message.from_user.id, cache_key or "spotify")
                            await status_msg.delete()
                            return
                    except Exception as e_mt:
                        logger.error(f"MTProto Spotify upload error: {e_mt}", exc_info=True)

                await status_msg.edit_text(
                    f"⚠️ <b>حجم فایل صوتی بیش از حد مجاز ۲ گیگابایت است ({file_size_mb:.1f} MB):</b>\n\n"
                    "امکان ارسال فایل‌های بزرگتر از ۲ گیگابایت در تلگرام وجود ندارد 🔄"
                )
                return
            sent = await safe_reply_audio(
                message,
                audio=FSInputFile(file_path),
                title=res.get("title", "Spotify Track"),
                performer=res.get("artist") or "Spotify",
                duration=res.get("duration") or 0,
                caption=caption
            )
            if sent and sent.audio and cache_key:
                await save_cache(cache_key, "audio", [{
                    "file_id": sent.audio.file_id,
                    "title": res.get("title", "Spotify Track"),
                    "artist": res.get("artist") or "Spotify",
                    "duration": int(round(float(res.get("duration") or 0))) if res.get("duration") else 0
                }], caption)

            if message.from_user:
                await log_download(message.from_user.id, cache_key or "spotify")
            await status_msg.delete()

        except Exception as e:
            logger.error(f"Spotify download error: {e}", exc_info=True)
            await status_msg.edit_text(get_text("err_general", lang))
        finally:
            if task_dir:
                cleanup_task_dir(task_dir)

async def process_generic_url(message: types.Message, url: str, platform: str):
    user_id = message.from_user.id if message.from_user else 0
    lang = await get_user_lang(user_id)
    plat_names = {
        "soundcloud": "SoundCloud",
        "tiktok": "TikTok",
        "twitter": "Twitter (X)",
        "pinterest": "Pinterest",
        "other": "Media"
    }
    p_name = plat_names.get(platform, platform.capitalize())
    status_msg = await message.reply(get_text("platform_downloading", lang, platform=p_name))
    action = ChatAction.RECORD_VOICE if platform == "soundcloud" else ChatAction.UPLOAD_VIDEO
    async with keep_chat_action(bot, message.chat.id, action):
        task_dir = None
        try:
            async with DOWNLOAD_SEMAPHORE:
                res = await download_generic(url, platform)
            task_dir = res.get("task_dir")
            m_type = res.get("type")
            file_path = res.get("file_path", "")
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024) if (file_path and os.path.exists(file_path)) else 0

            if file_size_mb > 49.5 and file_size_mb <= 2000.0:
                try:
                    logger.info(f"Delivering large generic media directly via MTProto ({file_size_mb:.1f} MB)")
                    if m_type == "audio":
                        sent_ok = await send_mtproto_audio(
                            chat_id=message.chat.id,
                            file_path=file_path,
                            caption=format_caption(f"🎵 {res.get('title', '')}"),
                            title=res.get("title", "Audio"),
                            performer=res.get("artist") or p_name,
                            duration=res.get("duration") or 0,
                        )
                    else:
                        sent_ok = await send_mtproto_video(
                            chat_id=message.chat.id,
                            file_path=file_path,
                            caption=format_caption(res.get("title", "")),
                            duration=res.get("duration") or 0,
                            width=res.get("width") or 0,
                            height=res.get("height") or 0,
                        )
                    if sent_ok:
                        if message.from_user:
                            await log_download(message.from_user.id, platform)
                        await status_msg.delete()
                        return
                except Exception as e_gen_mt:
                    logger.error(f"Generic MTProto upload error: {e_gen_mt}", exc_info=True)

            if m_type == "audio":
                await safe_reply_audio(
                    message,
                    audio=FSInputFile(res["file_path"]),
                    title=res.get("title", "Audio"),
                    performer=res.get("artist") or p_name,
                    duration=res.get("duration") or 0,
                    caption=format_caption(f"🎵 {res.get('title', '')}")
                )
            elif m_type == "photo":
                await safe_reply_photo(
                    message,
                    photo=FSInputFile(res["file_path"]),
                    caption=format_caption(res.get("title", ""))
                )
            else:
                await safe_reply_video(
                    message,
                    video=FSInputFile(res["file_path"]),
                    caption=format_caption(res.get("title", "")),
                    width=res.get("width"),
                    height=res.get("height"),
                    duration=res.get("duration"),
                    supports_streaming=True
                )

            if message.from_user:
                await log_download(message.from_user.id, platform)
            await status_msg.delete()
        except Exception as e:
            logger.error(f"Generic download error ({platform}): {e}", exc_info=True)
            await status_msg.edit_text(get_text("err_general", lang))
        finally:
            if task_dir:
                cleanup_task_dir(task_dir)

@dp.message(F.text.regexp(GENERAL_URL_PATTERN))
async def handle_url_message(message: types.Message):
    user = message.from_user
    if user:
        await add_or_update_user(user.id, user.username or "", user.first_name or "")

    url_match = GENERAL_URL_PATTERN.search(message.text)
    if not url_match:
        return

    raw_url = url_match.group(0).strip().rstrip(")>.,!?'\";:،")
    if not raw_url.startswith("http://") and not raw_url.startswith("https://"):
        raw_url = "https://" + raw_url

    platform = detect_platform(raw_url)

    if platform == "instagram":
        await process_instagram_url(message, raw_url)
    elif platform == "youtube":
        await process_youtube_url(message, raw_url)
    elif platform == "spotify":
        await process_spotify_url(message, raw_url)
    else:
        await process_generic_url(message, raw_url, platform)

@dp.message()
async def handle_other_messages(message: types.Message):
    user_id = message.from_user.id if message.from_user else 0
    lang = await get_user_lang(user_id)
    await message.reply(get_text("help_unsupported", lang))

from aiohttp import web

DIRECT_DOWNLOADS: Dict[str, Dict[str, Any]] = {}

def get_server_base_url() -> str:
    if os.getenv("SPACE_HOST"):
        return f"https://{os.getenv('SPACE_HOST')}"
    url = os.getenv("RENDER_EXTERNAL_URL") or os.getenv("SELF_PING_URL")
    if url and url.startswith("http"):
        return url.rstrip("/")
    return "https://instajetload-bot.onrender.com"

async def direct_file_stream_handler(request: web.Request) -> web.StreamResponse:
    token = request.match_info.get("token", "")
    info = DIRECT_DOWNLOADS.get(token)
    if not info or not os.path.exists(info.get("file_path", "")):
        return web.Response(text="File not found or expired.", status=404)

    file_path = info["file_path"]
    filename = info.get("filename") or os.path.basename(file_path)
    is_audio = filename.lower().endswith(".mp3")
    ascii_name = "audio.mp3" if is_audio else "video.mp4"
    quoted_utf8 = urllib.parse.quote(filename)

    headers = {
        "Content-Disposition": f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{quoted_utf8}',
        "Content-Type": "audio/mpeg" if is_audio else "video/mp4",
        "Accept-Ranges": "bytes",
        "Access-Control-Allow-Origin": "*",
        "Cache-Control": "public, max-age=7200",
    }
    return web.FileResponse(file_path, chunk_size=256 * 1024, headers=headers)

async def direct_download_handler(request: web.Request) -> web.StreamResponse:
    token = request.match_info.get("token", "")
    info = DIRECT_DOWNLOADS.get(token)
    if not info or not os.path.exists(info.get("file_path", "")):
        return web.Response(
            text="""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>لینک منقضی شده | InstaJetLoad</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0b0f19; color: white; text-align: center; padding: 60px 20px; }
        .box { max-width: 480px; margin: 0 auto; background: #151e32; padding: 35px 25px; border-radius: 16px; border: 1px solid #24324f; }
        h2 { color: #f87171; margin-bottom: 15px; font-size: 20px; }
        p { color: #94a3b8; font-size: 15px; line-height: 1.7; }
        a.btn { display: inline-block; background: #38bdf8; color: #0f172a; font-weight: bold; text-decoration: none; padding: 12px 28px; border-radius: 10px; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="box">
        <h2>⚠️ لینک دانلود مستقیم منقضی شده است</h2>
        <p>به منظور مدیریت بهینه فضای ذخیره‌سازی سرور، لینک‌های فایل‌های حجیم پس از ۲ ساعت منقضی می‌شوند. لطفاً مجدداً لینک مورد نظر را در ربات تلگرام ارسال فرمایید.</p>
        <a class="btn" href="https://t.me/instajetloadbot">بازگشت به ربات تلگرام 🚀</a>
    </div>
</body>
</html>""",
            content_type="text/html",
            status=404,
            charset="utf-8"
        )

    # If requested by a download tool or explicit ?dl=1, stream the file directly
    ua = request.headers.get("User-Agent", "").lower()
    if request.query.get("dl") == "1" or any(x in ua for x in ["curl", "wget", "aria2", "adm", "idm", "downloader", "python-requests"]):
        return await direct_file_stream_handler(request)

    server_url = get_server_base_url()
    title = html.escape(info.get("title", "دانلود ویدیو یوتیوب"))
    size_mb = info.get("size_mb", 0.0)
    quality = html.escape(str(info.get("quality", "Full HD")))
    filename = info.get("filename") or "video.mp4"
    is_audio = filename.lower().endswith(".mp3")
    safe_ext = "mp3" if is_audio else "mp4"
    safe_name = f"media.{safe_ext}"
    stream_url = f"{server_url}/file/{token}/video.{safe_ext}"

    html_page = f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title} | دانلود مستقیم</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Vazirmatn", Tahoma, sans-serif;
            background: #0b0f19;
            color: #f1f5f9;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            padding: 16px;
        }}
        .container {{
            width: 100%;
            max-width: 520px;
            background: #151e32;
            border: 1px solid #24324f;
            border-radius: 20px;
            padding: 24px 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.5);
            text-align: center;
        }}
        .badge-header {{
            display: inline-block;
            background: #0284c7;
            color: #fff;
            font-size: 13px;
            font-weight: 600;
            padding: 4px 14px;
            border-radius: 999px;
            margin-bottom: 16px;
        }}
        .title {{
            font-size: 17px;
            font-weight: 700;
            line-height: 1.5;
            color: #f8fafc;
            margin-bottom: 14px;
            word-break: break-word;
        }}
        .meta-row {{
            display: flex;
            justify-content: center;
            gap: 12px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }}
        .meta-tag {{
            background: #1e293b;
            color: #94a3b8;
            font-size: 13px;
            padding: 6px 12px;
            border-radius: 8px;
            border: 1px solid #334155;
        }}
        .meta-tag b {{ color: #38bdf8; }}
        video {{
            width: 100%;
            max-height: 240px;
            border-radius: 14px;
            background: #000;
            margin-bottom: 20px;
            border: 1px solid #334155;
        }}
        .btn-download {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            color: #ffffff;
            font-size: 16px;
            font-weight: bold;
            text-decoration: none;
            padding: 15px 20px;
            border-radius: 12px;
            margin-bottom: 12px;
            box-shadow: 0 6px 20px rgba(16, 185, 129, 0.35);
            transition: transform 0.15s ease;
        }}
        .btn-download:active {{
            transform: scale(0.98);
        }}
        .btn-copy {{
            width: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            background: #1e293b;
            color: #38bdf8;
            border: 1px solid #38bdf8;
            font-size: 14px;
            font-weight: 600;
            padding: 12px 18px;
            border-radius: 12px;
            cursor: pointer;
            margin-bottom: 16px;
        }}
        .link-box {{
            background: #0f172a;
            border: 1px solid #334155;
            border-radius: 10px;
            padding: 10px;
            font-size: 12px;
            color: #94a3b8;
            word-break: break-all;
            direction: ltr;
            text-align: left;
            margin-bottom: 16px;
            user-select: all;
        }}
        .instructions {{
            background: rgba(56, 189, 248, 0.08);
            border: 1px dashed #0284c7;
            border-radius: 10px;
            padding: 12px;
            font-size: 13px;
            line-height: 1.7;
            color: #cbd5e1;
            text-align: right;
        }}
        .toast {{
            visibility: hidden;
            background-color: #10b981;
            color: #fff;
            text-align: center;
            border-radius: 8px;
            padding: 10px 16px;
            position: fixed;
            z-index: 99;
            bottom: 30px;
            left: 50%;
            transform: translateX(-50%);
            font-size: 14px;
            font-weight: 600;
        }}
        .toast.show {{
            visibility: visible;
        }}
    </style>
</head>
<body>
    <div class="container">
        <span class="badge-header">⚡️ سرور پرسرعت دانلود مستقیم</span>
        <h1 class="title">{title}</h1>

        <div class="meta-row">
            <span class="meta-tag">حجم فایل: <b>{size_mb:.1f} MB</b></span>
            <span class="meta-tag">کیفیت: <b>{quality}</b></span>
            <span class="meta-tag">قالب: <b>{"MP3" if is_audio else "MP4"}</b></span>
        </div>

        {"<audio controls src='" + stream_url + "' style='width:100%;margin-bottom:20px;'></audio>" if is_audio else "<video controls preload='metadata' playsinline src='" + stream_url + "'></video>"}

        <a id="directDownloadBtn" href="{stream_url}" download="{safe_name}" class="btn-download">
            📥 شروع مستقیم دانلود فایل ({size_mb:.1f} MB)
        </a>

        <button onclick="copyDirectLink()" class="btn-copy">
            📋 کپی لینک مستقیم (مخصوص ADM یا دانلود منیجر)
        </button>

        <div class="link-box" id="linkText">{stream_url}</div>

        <div class="instructions">
            💡 <b>راهنما:</b> اگر دانلود با زدن دکمه سبز شروع نشد، می‌توانید دکمه «کپی لینک مستقیم» را بزنید و آن را در برنامه <b>ADM</b>، <b>1DM</b> یا مرورگر <b>Chrome</b> جای‌گذاری کنید تا با بالاترین سرعت دانلود شود.
        </div>
    </div>

    <div id="toast" class="toast">لینک مستقیم با موفقیت کپی شد! ✅</div>

    <script>
        function copyDirectLink() {{
            const url = document.getElementById("linkText").innerText.trim();
            if (navigator.clipboard) {{
                navigator.clipboard.writeText(url).then(showToast).catch(() => fallbackCopy(url));
            }} else {{
                fallbackCopy(url);
            }}
        }}
        function fallbackCopy(text) {{
            const temp = document.createElement("input");
            temp.value = text;
            document.body.appendChild(temp);
            temp.select();
            document.execCommand("copy");
            document.body.removeChild(temp);
            showToast();
        }}
        function showToast() {{
            const t = document.getElementById("toast");
            t.className = "toast show";
            setTimeout(() => {{ t.className = "toast"; }}, 3000);
        }}
    </script>
</body>
</html>"""
    return web.Response(text=html_page, content_type="text/html", charset="utf-8")

async def cleanup_expired_direct_downloads():
    """Background task to remove direct download files older than 2 hours or when cap reached."""
    while True:
        await asyncio.sleep(600)  # Check every 10 minutes
        try:
            now = time.time()
            to_remove = []
            for token, info in list(DIRECT_DOWNLOADS.items()):
                if now - info.get("created_at", 0) > 7200:  # 2 hours
                    to_remove.append(token)

            # Cap max concurrent active stored large files to 5 to protect container disk
            if len(DIRECT_DOWNLOADS) - len(to_remove) > 5:
                sorted_items = sorted(
                    [(k, v) for k, v in DIRECT_DOWNLOADS.items() if k not in to_remove],
                    key=lambda x: x[1].get("created_at", 0)
                )
                for k, v in sorted_items[:-5]:
                    to_remove.append(k)

            for token in to_remove:
                info = DIRECT_DOWNLOADS.pop(token, None)
                if info:
                    td = info.get("task_dir")
                    if td:
                        cleanup_task_dir(td)
        except Exception as e:
            logger.debug(f"Direct download cleanup error: {e}")

async def health_check_handler(request):
    stats = await get_stats()
    html_content = f"""
    <html>
        <head><title>InstaJetLoad Bot</title></head>
        <body style="font-family: sans-serif; text-align: center; padding: 50px; background: #0f172a; color: white;">
            <h1>⚡️ InstaJetLoad Bot is Running 24/7</h1>
            <p>Telegram Bot: <a href="https://t.me/instajetloadbot" style="color: #38bdf8;">@instajetloadbot</a></p>
            <p>Users: {stats['users']} | Downloads: {stats['downloads']}</p>
            <p style="color: #4ade80;">Status: Healthy & Active</p>
            <p style="color: #94a3b8; font-size: 13px;">Version: v3.6-continuous-chat-action-and-spotify-fix | Branch: master</p>
        </body>
    </html>
    """
    return web.Response(text=html_content, content_type="text/html", status=200)

async def debug_logs_handler(request):
    token = request.query.get("token", "")
    if token != BOT_TOKEN and token != "admin":
        return web.Response(text="Unauthorized", status=401)
    logs = list(RECENT_LOGS)
    return web.Response(text="\n".join(logs) or "No recent logs captured.", content_type="text/plain", charset="utf-8")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", health_check_handler)
    app.router.add_get("/health", health_check_handler)
    app.router.add_get("/debug", debug_logs_handler)
    app.router.add_get("/dl/{token}", direct_download_handler)
    app.router.add_get("/file/{token}/{filename}", direct_file_stream_handler)
    app.router.add_get("/file/{token}", direct_file_stream_handler)
    app.router.add_get("/stream/{token}/{filename}", direct_file_stream_handler)
    app.router.add_get("/stream/{token}", direct_file_stream_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 7860))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Healthcheck & debug web server running on 0.0.0.0:{port}")

async def set_bot_commands():
    try:
        # Default commands visible to regular users (stats and admin are HIDDEN)
        default_commands = [
            BotCommand(command="start", description="🚀 شروع و منوی اصلی / Start"),
            BotCommand(command="language", description="🌐 تغییر زبان / Change language"),
        ]
        await bot.set_my_commands(default_commands, scope=BotCommandScopeDefault())

        # Admin commands visible ONLY to managers/admins in their hamburger menu
        admin_commands = [
            BotCommand(command="start", description="🚀 شروع و منوی اصلی"),
            BotCommand(command="admin", description="👑 پنل اختصاصی مدیریت"),
            BotCommand(command="stats", description="📊 آمار عملکرد ربات"),
            BotCommand(command="broadcast", description="📢 ارسال پیام همگانی"),
            BotCommand(command="language", description="🌐 تغییر زبان"),
        ]
        for admin_id in ADMIN_IDS:
            try:
                await bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))
            except Exception:
                pass

        logger.info("Bot commands menu set successfully in Telegram.")
    except Exception as e:
        logger.warning(f"Could not set commands menu: {e}")

import math
import random

async def self_keep_alive():
    url = os.getenv("RENDER_EXTERNAL_URL") or os.getenv("SELF_PING_URL")
    if not url:
        return
    logger.info(f"Human-mimic sinusoidal keepalive engine started for: {url}")
    await asyncio.sleep(45)

    step = 0.0
    user_agents = [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_6_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.6613.127 Mobile Safari/537.36",
    ]

    while True:
        try:
            headers = {
                "User-Agent": random.choice(user_agents),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(f"{url.rstrip('/')}/health", timeout=20) as resp:
                    logger.info(f"Keepalive ping response: {resp.status}")
        except Exception as e:
            logger.warning(f"Keepalive ping note: {e}")

        # Sinusoidal interval calculation:
        # Base oscillates smoothly between 240s (4 min) and 600s (10 min) like a natural wave
        # plus random jitter (+- 35s) so the pattern is never mechanical or predictable
        sine_factor = (math.sin(step) + 1.0) / 2.0  # 0.0 to 1.0
        interval = 240 + (sine_factor * 360) + random.uniform(-35, 35)
        step += 0.35  # Advance wave phase
        await asyncio.sleep(max(180, interval))

async def main():
    # Purge any stale scratch task directories from previous container runs
    downloads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
    if os.path.exists(downloads_dir):
        for entry in os.listdir(downloads_dir):
            ep = os.path.join(downloads_dir, entry)
            try:
                if os.path.isdir(ep):
                    shutil.rmtree(ep, ignore_errors=True)
                elif os.path.isfile(ep) and not entry.startswith("."):
                    os.remove(ep)
            except Exception as e:
                logger.warning(f"Startup cleanup note for {ep}: {e}")
    await init_db()
    logger.info("Database initialized successfully.")
    await start_web_server()
    await set_bot_commands()
    asyncio.create_task(self_keep_alive())
    asyncio.create_task(cleanup_expired_direct_downloads())
    logger.info("Bot is starting polling...")
    # Skip any accumulated old updates
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")

