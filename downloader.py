import os
import shutil
import uuid
import asyncio
import re
import glob
from typing import Optional, Dict, Any, List
import yt_dlp

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")
COOKIES_FILE = os.path.join(BASE_DIR, "cookies.txt")

os.makedirs(DOWNLOADS_DIR, exist_ok=True)

INSTA_URL_REGEX = re.compile(
    r"(?:https?:\/\/)?(?:www\.)?(?:instagram\.com|instagr\.am)\/(?:p|reel|reels|tv|share\/(?:reel|p))\/([A-Za-z0-9_-]+)",
    re.IGNORECASE
)

def extract_shortcode(url: str) -> Optional[str]:
    match = INSTA_URL_REGEX.search(url)
    if match:
        return match.group(1)
    return None

def _download_sync(url: str) -> Dict[str, Any]:
    task_id = str(uuid.uuid4())
    task_dir = os.path.join(DOWNLOADS_DIR, task_id)
    os.makedirs(task_dir, exist_ok=True)

    ydl_opts: Dict[str, Any] = {
        "outtmpl": os.path.join(task_dir, "%(id)s_%(playlist_index)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
        "extract_flat": False,
        "retries": 3,
        "socket_timeout": 30,
    }

    if os.path.exists(COOKIES_FILE) and os.path.getsize(COOKIES_FILE) > 0:
        ydl_opts["cookiefile"] = COOKIES_FILE

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        if not info:
            raise ValueError("نمی‌توان اطلاعات این پست را دریافت کرد.")

        shortcode = info.get("id") or extract_shortcode(url) or task_id
        caption = info.get("description") or info.get("title") or ""

        # Find downloaded files in task_dir
        downloaded_files = glob.glob(os.path.join(task_dir, "*"))
        # Exclude temporary parts
        downloaded_files = [
            f for f in downloaded_files
            if not f.endswith(".part") and not f.endswith(".ytdl") and os.path.isfile(f)
        ]

        if not downloaded_files:
            raise ValueError("فایلی برای دانلود یافت نشد.")

        # Sort files to keep carousel slide order
        downloaded_files.sort()

        items: List[Dict[str, str]] = []
        for file_path in downloaded_files:
            ext = os.path.splitext(file_path)[1].lower()
            if ext in [".mp4", ".mov", ".mkv", ".webm"]:
                media_type = "video"
            elif ext in [".jpg", ".jpeg", ".png", ".webp"]:
                media_type = "photo"
            else:
                media_type = "document"

            items.append({
                "type": media_type,
                "path": file_path
            })

        return {
            "shortcode": shortcode,
            "caption": caption,
            "task_dir": task_dir,
            "items": items
        }

async def download_instagram_media(url: str) -> Dict[str, Any]:
    """Run yt-dlp download in thread pool to prevent blocking the event loop."""
    return await asyncio.to_thread(_download_sync, url)

def cleanup_task_dir(task_dir: str):
    """Safely remove the temporary folder and its downloaded files."""
    try:
        if task_dir and os.path.exists(task_dir):
            shutil.rmtree(task_dir, ignore_errors=True)
    except Exception as e:
        print(f"Error cleaning task dir {task_dir}: {e}")
