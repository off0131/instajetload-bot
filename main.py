import asyncio
import logging
import os
import re
import html
from typing import List

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
)
from aiogram.enums import ChatAction, ParseMode
from aiogram.client.default import DefaultBotProperties

from database import init_db, add_or_update_user, get_cached, save_cache, log_download, get_stats
from downloader import download_instagram_media, cleanup_task_dir, extract_shortcode

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

def get_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⚡️ وضعیت سرعت ربات", callback_data="ping"),
                InlineKeyboardButton(text="💡 نکات دانلود سریع", callback_data="tips"),
            ],
            [
                InlineKeyboardButton(text="🚀 معرفی به دوستان", switch_inline_query="بهترین ربات دانلود سریع از اینستاگرام: @instajetloadbot 🔥"),
            ]
        ]
    )

@dp.message(CommandStart())
async def handle_start(message: types.Message):
    user = message.from_user
    if user:
        await add_or_update_user(user.id, user.username or "", user.first_name or "")

    name = user.first_name if user else "دوست من"
    welcome_text = (
        f"سلام {name} عزیز! خیلی خوش اومدی 🤩❤️✨\n\n"
        "من اینجام تا هرچیزی از اینستاگرام خواستی رو با <b>بالاترین کیفیت و سرعت برق‌آسا</b> برات دانلود کنم ⚡️🎯\n\n"
        "🔥 <b>چی برات دانلود می‌کنم؟</b>\n"
        "▫️ <b>ریلز (Reels):</b> کیفیت اصلی بدون افت فریم 🎬\n"
        "▫️ <b>عکس‌ها:</b> وضوح شفاف و کامل بدون کات شدن 📸\n"
        "▫️ <b>آلبوم‌ها و اسلایدها:</b> تمام عکس‌ها و فیلم‌ها باهم 🗂\n"
        "▫️ <b>متن کپشن:</b> همراه با ایموجی‌ها و هشتگ‌ها ✍️\n\n"
        "👇 <b>همین الان امتحانش کن:</b>\n"
        "فقط کافیه لینک پست یا ریلز رو برام بفرستی تا در چند ثانیه تحویلت بدم! 😉🚀"
    )
    await message.answer(welcome_text, reply_markup=get_main_keyboard())

@dp.callback_query(F.data == "ping")
async def cb_ping(callback: types.CallbackQuery):
    await callback.answer("🟢 سرور کاملاً بیداره و سرعت دانلود در حداکثر توان قرار داره! ⚡️🏎", show_alert=True)

@dp.callback_query(F.data == "tips")
async def cb_tips(callback: types.CallbackQuery):
    tips_text = (
        "💡 <b>چندتا نکته خودمانی برای دانلود راحت‌تر:</b> ✨\n\n"
        "۱. برای کپی کردن لینک، زیر هر ریلز یا پست دکمه <b>Share (فلش یا موشک کاغذی)</b> رو بزن و <b>Copy link</b> رو انتخاب کن 📲\n\n"
        "۲. پیج حتماً باید عمومی (Public) باشه تا محتواش بدون معطلی دانلود بشه 🔓\n\n"
        "۳. اگه ویدیویی رو قبلاً کسی دانلود کرده باشه، ربات اون رو آنی و در کمتر از یک ثانیه برات می‌فرسته! ⚡️"
    )
    await callback.message.answer(tips_text)
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

INSTA_PATTERN = re.compile(r"https?:\/\/(?:www\.)?(?:instagram\.com|instagr\.am)\/\S+", re.IGNORECASE)

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

@dp.message(F.text.regexp(INSTA_PATTERN))
async def handle_instagram_link(message: types.Message):
    user = message.from_user
    if user:
        await add_or_update_user(user.id, user.username or "", user.first_name or "")

    url_match = INSTA_PATTERN.search(message.text)
    if not url_match:
        return

    url = url_match.group(0).strip()
    shortcode = extract_shortcode(url)

    status_msg = await message.reply("⚡️ دریافت شد! در حال دانلود با بالاترین کیفیت... لطفاً چند ثانیه صبر کن رفیق ⏳🏎")
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
            # Telegram supports max 10 per media group
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

        # Save to database cache
        if saved_file_ids and sc:
            await save_cache(sc, "album" if len(items) > 1 else items[0]["type"], saved_file_ids, caption)

        if user:
            await log_download(user.id, sc)

        await status_msg.delete()

    except Exception as e:
        logger.error(f"Download error: {e}", exc_info=True)
        err_msg = str(e)
        if "private" in err_msg.lower() or "followers" in err_msg.lower():
            text = (
                "🔒 <b>پیج یا پست خصوصیه (Private):</b>\n\n"
                "رفیق، اینستاگرام اجازه دانلود از پیج‌های قفل‌شده و پرایوت رو بدون لاگین نمیده 🥺💔\n"
                "لطفاً مطمئن شو پیج عمومیه (Public) تا بتونم با بالاترین کیفیت برات دانلودش کنم! ✨"
            )
        elif "Unsupported URL" in err_msg:
            text = "🧐 <b>لینک نامعتبره!</b>\n\nلطفاً لینک کامل یک پست، ریلز یا استوری از اینستاگرام رو برام بفرست دوست من 🌸"
        else:
            text = (
                "⚠️ <b>یه مشکلی پیش اومد:</b>\n\n"
                "اینستاگرام موقتاً پاسخی نداد یا ترافیک این بخش زیاده 🙁\n"
                "چند لحظه بعد دوباره لینکش رو بفرست تا تلاشمو بکنم! 🔄❤️"
            )

        await status_msg.edit_text(text)

    finally:
        if task_dir:
            cleanup_task_dir(task_dir)

@dp.message()
async def handle_other_messages(message: types.Message):
    await message.reply(
        "👋 سلام رفیق!\n\n"
        "من فقط لینک‌های اینستاگرام رو پردازش و دانلود می‌کنم ⚡️📱\n"
        "کافیه لینک هر ریلز، ویدیو، آلبوم یا عکسی رو که می‌خوای برام بفرستی تا سریع تحویلت بدم! 😉👇\n\n"
        "<i>مثال:</i>\n"
        "<code>https://www.instagram.com/reel/C8P6bOUIa-X/</code>"
    )

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
            <p style="color: #94a3b8; font-size: 13px;">Version: v2.3-h264-fullvideo | Branch: master</p>
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

from aiogram.types import BotCommandScopeChat

async def set_bot_commands():
    try:
        # Default commands visible to regular users
        default_commands = [
            BotCommand(command="start", description="🚀 شروع و منوی اصلی ربات"),
        ]
        await bot.set_my_commands(default_commands, scope=BotCommandScopeDefault())

        # Admin commands with stats
        admin_commands = [
            BotCommand(command="start", description="🚀 شروع و منوی اصلی ربات"),
            BotCommand(command="stats", description="📊 آمار عملکرد ربات (پنل ادمین)"),
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

