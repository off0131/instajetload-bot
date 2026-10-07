import asyncio
import logging
import os
import re
import html
from typing import List

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
    download_generic,
)

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

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

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
                InlineKeyboardButton(text=get_text("btn_server_status", lang), callback_data="ping"),
                InlineKeyboardButton(text=get_text("btn_tips", lang), callback_data="tips"),
            ],
            [
                InlineKeyboardButton(text=get_text("btn_change_lang", lang), callback_data="change_lang"),
            ],
            [
                InlineKeyboardButton(text=get_text("btn_share", lang), switch_inline_query=get_text("share_text", lang)),
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

@dp.callback_query(F.data == "ping")
async def cb_ping(callback: types.CallbackQuery):
    user_id = callback.from_user.id if callback.from_user else 0
    lang = await get_user_lang(user_id)
    await callback.answer(get_text("ping_alert", lang), show_alert=True)

@dp.callback_query(F.data == "tips")
async def cb_tips(callback: types.CallbackQuery):
    user_id = callback.from_user.id if callback.from_user else 0
    lang = await get_user_lang(user_id)
    await callback.message.answer(get_text("tips_content", lang))
    await callback.answer()

@dp.message(Command("stats"))
async def handle_cmd_stats(message: types.Message):
    user_id = message.from_user.id if message.from_user else 0
    if not is_admin(user_id):
        await message.answer("⛔️ این بخش خصوصی و مختص ادمین ربات هستش 😉")
        return

    stats = await get_stats()
    text = (
        "<b>📊 وضعیت عملکرد ربات (پنل اختصاصی ادمین):</b> 👑\n\n"
        f"👥 تعداد کل کاربران: <b>{stats['users']}</b> نفر 🔥\n"
        f"📥 تعداد دانلودهای موفق: <b>{stats['downloads']}</b> بار ⚡️\n"
        f"💾 فایل‌های ذخیره شده در کش: <b>{stats['cached']}</b> عدد 🚀\n"
        "🟢 سرور ابری: <b>Online & Active 24/7 (Render)</b>"
    )
    await message.answer(text)

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

truncate_caption = format_caption

async def process_instagram_url(message: types.Message, url: str):
    user = message.from_user
    user_id = user.id if user else 0
    lang = await get_user_lang(user_id)
    shortcode = extract_shortcode(url)

    status_msg = await message.reply(get_text("downloading_general", lang))
    await bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_VIDEO)

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
                            await message.reply_video(
                                video=item["file_id"],
                                caption=caption_text,
                                width=item.get("width"),
                                height=item.get("height"),
                                duration=item.get("duration"),
                                supports_streaming=True
                            )
                        else:
                            await message.reply_photo(photo=item["file_id"], caption=caption_text)
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
                                    duration=itm.get("duration"),
                                    supports_streaming=True
                                ))
                            else:
                                media_group.append(InputMediaPhoto(media=itm["file_id"], caption=c))
                        await message.reply_media_group(media=media_group)

                    await log_download(user.id if user else 0, shortcode)
                    await status_msg.delete()
                    return
                except Exception as e:
                    logger.warning(f"Cache delivery failed, downloading freshly: {e}")

    # 2. Download freshly
    task_dir = None
    try:
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
                sent = await message.reply_video(
                    video=file_input,
                    caption=formatted_caption,
                    width=item.get("width"),
                    height=item.get("height"),
                    duration=item.get("duration"),
                    supports_streaming=True
                )
                if sent.video:
                    saved_file_ids.append({
                        "type": "video",
                        "file_id": sent.video.file_id,
                        "width": item.get("width"),
                        "height": item.get("height"),
                        "duration": item.get("duration")
                    })
            elif item["type"] == "photo":
                sent = await message.reply_photo(photo=file_input, caption=formatted_caption)
                if sent.photo:
                    saved_file_ids.append({"type": "photo", "file_id": sent.photo[-1].file_id})
            else:
                sent = await message.reply_document(document=file_input, caption=formatted_caption)
                if sent.document:
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
                            duration=itm.get("duration"),
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
    try:
        info = await get_youtube_info(url)
        video_id = info["id"]
        title = info.get("title", "YouTube Video")
        duration = info.get("duration", 0)
        dur_str = f"{duration // 60}:{duration % 60:02d}" if duration else "0:00"
        channel = info.get("channel", "YouTube")
        resolutions = info.get("resolutions") or [720, 480, 360]

        # Build inline keyboard for quality selection
        quality_buttons = []
        row = []
        for r in resolutions[:4]:
            row.append(InlineKeyboardButton(text=f"🎬 {r}p", callback_data=f"yt:{video_id}:{r}"))
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
    quality_label = get_text("yt_audio_btn", lang) if quality == "audio" else f"{quality}p"
    status_msg = await callback.message.reply(get_text("yt_downloading", lang, quality=quality_label))

    if quality == "audio":
        await bot.send_chat_action(callback.message.chat.id, ChatAction.RECORD_VOICE)
    else:
        await bot.send_chat_action(callback.message.chat.id, ChatAction.UPLOAD_VIDEO)

    task_dir = None
    try:
        res = await download_youtube(video_id, quality)
        task_dir = res.get("task_dir")
        file_path = res.get("file_path")

        if quality == "audio":
            await callback.message.reply_audio(
                audio=FSInputFile(file_path),
                title=res.get("title", "YouTube Audio"),
                performer=res.get("artist") or "YouTube",
                duration=res.get("duration") or 0,
                caption=format_caption(f"🎵 {res.get('title', '')}")
            )
        else:
            await callback.message.reply_video(
                video=FSInputFile(file_path),
                caption=format_caption(res.get("title", "")),
                width=res.get("width"),
                height=res.get("height"),
                duration=res.get("duration"),
                supports_streaming=True
            )

        if callback.from_user:
            await log_download(callback.from_user.id, f"yt_{video_id}")
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
    await bot.send_chat_action(message.chat.id, ChatAction.RECORD_VOICE)
    task_dir = None
    try:
        res = await download_spotify(url)
        task_dir = res.get("task_dir")
        await message.reply_audio(
            audio=FSInputFile(res["file_path"]),
            title=res.get("title", "Spotify Track"),
            performer=res.get("artist") or "Spotify",
            duration=res.get("duration") or 0,
            caption=format_caption(f"🎵 {res.get('title', '')}\n👤 {res.get('artist', '')}")
        )
        if message.from_user:
            await log_download(message.from_user.id, "spotify")
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
    task_dir = None
    try:
        res = await download_generic(url, platform)
        task_dir = res.get("task_dir")
        m_type = res.get("type")

        if m_type == "audio":
            await message.reply_audio(
                audio=FSInputFile(res["file_path"]),
                title=res.get("title", "Audio"),
                performer=res.get("artist") or p_name,
                duration=res.get("duration") or 0,
                caption=format_caption(f"🎵 {res.get('title', '')}")
            )
        elif m_type == "photo":
            await message.reply_photo(
                photo=FSInputFile(res["file_path"]),
                caption=format_caption(res.get("title", ""))
            )
        else:
            await message.reply_video(
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
            <p style="color: #94a3b8; font-size: 13px;">Version: v2.4-multiplatform-fixed | Branch: master</p>
        </body>
    </html>
    """
    return web.Response(text=html_content, content_type="text/html", status=200)

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", health_check_handler)
    app.router.add_get("/health", health_check_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 7860))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Healthcheck web server running on 0.0.0.0:{port}")

async def set_bot_commands():
    try:
        # Default commands visible to regular users
        default_commands = [
            BotCommand(command="start", description="🚀 Start / شروع"),
            BotCommand(command="language", description="🌐 Change language / تغییر زبان"),
        ]
        await bot.set_my_commands(default_commands, scope=BotCommandScopeDefault())

        # Admin commands with stats
        admin_commands = [
            BotCommand(command="start", description="🚀 Start / شروع"),
            BotCommand(command="language", description="🌐 Change language / تغییر زبان"),
            BotCommand(command="stats", description="📊 Bot Stats (Admin)"),
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
    await init_db()
    logger.info("Database initialized successfully.")
    await start_web_server()
    await set_bot_commands()
    asyncio.create_task(self_keep_alive())
    logger.info("Bot is starting polling...")
    # Skip any accumulated old updates
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")

