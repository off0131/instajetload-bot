import os
import shutil
import uuid
import asyncio
import re
import glob
import subprocess
import json
import urllib.request
import html
from typing import Optional, Dict, Any, List
import yt_dlp
from hachoir.parser import createParser
from hachoir.metadata import extractMetadata

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")
COOKIES_FILE = os.path.join(BASE_DIR, "cookies.txt")

os.makedirs(DOWNLOADS_DIR, exist_ok=True)

INSTA_URL_REGEX = re.compile(
    r"(?:https?:\/\/)?(?:www\.)?(?:instagram\.com|instagr\.am)\/(?:p|reel|reels|tv|share\/(?:reel|p)|stories\/[^\/\s]+)\/([A-Za-z0-9_-]+)",
    re.IGNORECASE
)

def extract_shortcode(url: str) -> Optional[str]:
    match = INSTA_URL_REGEX.search(url)
    if match:
        return match.group(1)
    return None

def get_media_dimensions(file_path: str):
    """Extract exact width, height, and duration from video or image."""
    width, height, duration = None, None, None
    try:
        parser = createParser(file_path)
        if parser:
            with parser:
                metadata = extractMetadata(parser)
                if metadata:
                    if metadata.has("width"):
                        width = int(metadata.get("width"))
                    if metadata.has("height"):
                        height = int(metadata.get("height"))
                    if metadata.has("duration"):
                        duration = int(metadata.get("duration").seconds)
    except Exception as e:
        print(f"Metadata extraction error for {file_path}: {e}")
    return width, height, duration

def _download_with_ytdlp(url: str, task_dir: str) -> Dict[str, Any]:
    ydl_opts: Dict[str, Any] = {
        "outtmpl": os.path.join(task_dir, "%(id)s_%(playlist_index)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
        "extract_flat": False,
        "retries": 2,
        "socket_timeout": 20,
    }

    if os.path.exists(COOKIES_FILE) and os.path.getsize(COOKIES_FILE) > 0:
        ydl_opts["cookiefile"] = COOKIES_FILE

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        if not info:
            return {}

        caption = info.get("description") or info.get("title") or ""
        shortcode = info.get("id") or extract_shortcode(url) or ""
        return {"caption": caption, "shortcode": shortcode}

def _download_with_gallery_dl(url: str, task_dir: str) -> Dict[str, Any]:
    gallery_dl_bin = os.path.join(BASE_DIR, "venv", "bin", "gallery-dl")
    if not os.path.exists(gallery_dl_bin):
        gallery_dl_bin = "gallery-dl"

    cmd = [
        gallery_dl_bin,
        "--directory", task_dir,
        "--write-metadata",
        "--no-mtime",
        "--retries", "2",
        "--timeout", "25",
    ]

    if os.path.exists(COOKIES_FILE) and os.path.getsize(COOKIES_FILE) > 0:
        cmd.extend(["--cookies", COOKIES_FILE])

    cmd.append(url)

    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=90)
        caption = ""
        meta_files = glob.glob(os.path.join(task_dir, "**", "*.json"), recursive=True)
        for mf in meta_files:
            try:
                with open(mf, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                    c = meta.get("caption") or meta.get("description") or ""
                    if c and len(c) > len(caption):
                        caption = c
            except Exception:
                pass
        return {"caption": caption}
    except Exception as e:
        print(f"gallery-dl error: {e}")
        return {}

def _download_uncropped_photo_and_caption(shortcode: str, url: str, task_dir: str) -> Dict[str, Any]:
    """Downloads original full-resolution uncropped photo (not the 640x640 square crop) and gets caption."""
    # Never scrape a Reel or Video link as a photo!
    if "/reel/" in url.lower() or "/reels/" in url.lower():
        return {}

    caption = ""
    # 1. Fetch caption via OpenGraph metadata
    try:
        clean_url = url.split("?")[0]
        req_og = urllib.request.Request(
            clean_url,
            headers={"User-Agent": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)"}
        )
        with urllib.request.urlopen(req_og, timeout=12) as r_og:
            page = r_og.read().decode("utf-8")
        descs = [html.unescape(m) for m in re.findall(r'property="og:description"\s+content="([^"]+)"', page)]
        if descs:
            caption = descs[0]
            if '": "' in caption:
                caption = caption.split('": "', 1)[1].rstrip('"\u200e .')
    except Exception as e:
        print(f"Caption fetch error: {e}")

    # 2. Download original uncropped image (size=l gives full original aspect ratio 1080p, not square)
    try:
        direct_url = f"https://www.instagram.com/p/{shortcode}/media/?size=l"
        req = urllib.request.Request(
            direct_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            content_type = resp.headers.get("Content-Type", "")
            if "image" not in content_type.lower():
                return {"caption": caption}
            data = resp.read()
            if len(data) > 5000:
                target_path = os.path.join(task_dir, "00_original_photo.jpg")
                with open(target_path, "wb") as f_out:
                    f_out.write(data)
                return {"caption": caption}
    except Exception as e:
        print(f"Direct uncropped size=l download error: {e}")

    return {"caption": caption}

def _download_sync(url: str) -> Dict[str, Any]:
    task_id = str(uuid.uuid4())
    task_dir = os.path.join(DOWNLOADS_DIR, task_id)
    os.makedirs(task_dir, exist_ok=True)

    caption = ""
    shortcode = extract_shortcode(url) or task_id

    def get_valid_files():
        all_f = glob.glob(os.path.join(task_dir, "**", "*"), recursive=True)
        return [
            f for f in all_f
            if os.path.isfile(f)
            and not f.endswith(".part")
            and not f.endswith(".ytdl")
            and not f.endswith(".json")
        ]

    # 1. First attempt: yt-dlp (downloads original video stream in native resolution)
    try:
        ytdl_res = _download_with_ytdlp(url, task_dir)
        caption = ytdl_res.get("caption", "")
        if ytdl_res.get("shortcode"):
            shortcode = ytdl_res["shortcode"]
    except Exception as e:
        print(f"yt-dlp attempt note: {e}")

    downloaded_files = get_valid_files()

    # 2. Second attempt: gallery-dl (multi-slide carousels and stories with cookies)
    if not downloaded_files:
        gdl_res = _download_with_gallery_dl(url, task_dir)
        if not caption:
            caption = gdl_res.get("caption", "")
        downloaded_files = get_valid_files()

    # 3. Third attempt: Uncropped full-resolution photo scraper
    if not downloaded_files and shortcode:
        # If it was explicitly a /reel/ link, don't download a photo!
        if "/reel/" not in url.lower() and "/reels/" not in url.lower():
            photo_res = _download_uncropped_photo_and_caption(shortcode, url, task_dir)
            if not caption:
                caption = photo_res.get("caption", "")
            downloaded_files = get_valid_files()

    if not downloaded_files:
        if "/reel/" in url.lower() or "/reels/" in url.lower():
            raise ValueError(
                "خطا در دریافت ویدیو: این ریلز خصوصی (Private) است یا به علت محدودیت‌های جدید اینستاگرام نیاز به کوکی دارد."
            )
        raise ValueError(
            "اینستاگرام برای دانلود این پست یا استوری نیاز به لاگین دارد یا پیج خصوصی (Private) است."
        )

    downloaded_files.sort()

    items: List[Dict[str, Any]] = []
    for file_path in downloaded_files:
        ext = os.path.splitext(file_path)[1].lower()
        if ext in [".mp4", ".mov", ".mkv", ".webm"]:
            media_type = "video"
        elif ext in [".jpg", ".jpeg", ".png", ".webp"]:
            media_type = "photo"
        else:
            media_type = "document"

        # Extract precise dimensions and duration
        w, h, dur = get_media_dimensions(file_path)

        items.append({
            "type": media_type,
            "path": file_path,
            "width": w,
            "height": h,
            "duration": dur,
        })

    return {
        "shortcode": shortcode,
        "caption": caption,
        "task_dir": task_dir,
        "items": items
    }

async def download_instagram_media(url: str) -> Dict[str, Any]:
    """Run download in thread pool to prevent blocking the event loop."""
    return await asyncio.to_thread(_download_sync, url)

def cleanup_task_dir(task_dir: str):
    """Safely remove the temporary folder and its downloaded files."""
    try:
        if task_dir and os.path.exists(task_dir):
            shutil.rmtree(task_dir, ignore_errors=True)
    except Exception as e:
        print(f"Error cleaning task dir {task_dir}: {e}")
