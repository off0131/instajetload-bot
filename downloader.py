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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")
COOKIES_FILE = os.path.join(BASE_DIR, "cookies.txt")

os.makedirs(DOWNLOADS_DIR, exist_ok=True)

# Regex supporting posts (/p/), reels (/reel/ or /reels/), and stories (/stories/user/id/)
INSTA_URL_REGEX = re.compile(
    r"(?:https?:\/\/)?(?:www\.)?(?:instagram\.com|instagr\.am)\/(?:p|reel|reels|tv|share\/(?:reel|p)|stories\/[^\/\s]+)\/([A-Za-z0-9_-]+)",
    re.IGNORECASE
)

def extract_shortcode(url: str) -> Optional[str]:
    match = INSTA_URL_REGEX.search(url)
    if match:
        return match.group(1)
    return None

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
    """Fallback engine using gallery-dl for image posts, carousels, and stories."""
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

def _download_with_opengraph(url: str, task_dir: str) -> Dict[str, Any]:
    """Direct scraper mimicking Meta/Facebook crawlers to bypass login on photo posts."""
    try:
        # Clean URL
        clean_url = url.split("?")[0]
        req = urllib.request.Request(
            clean_url,
            headers={
                "User-Agent": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            page = r.read().decode("utf-8")

        images = [html.unescape(m) for m in re.findall(r'property="og:image"\s+content="([^"]+)"', page)]
        videos = [html.unescape(m) for m in re.findall(r'property="og:video(?::secure_url)?"\s+content="([^"]+)"', page)]
        descs = [html.unescape(m) for m in re.findall(r'property="og:description"\s+content="([^"]+)"', page)]

        caption = descs[0] if descs else ""
        # Clean caption from "X likes, Y comments - User on Date: " prefix if present
        if '": "' in caption:
            caption = caption.split('": "', 1)[1].rstrip('"\u200e .')

        # Download media
        downloaded = False
        if videos:
            target_path = os.path.join(task_dir, "00_video.mp4")
            req_v = urllib.request.Request(videos[0], headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req_v, timeout=30) as r_v:
                with open(target_path, "wb") as f_out:
                    f_out.write(r_v.read())
            downloaded = True

        if not downloaded and images:
            target_path = os.path.join(task_dir, "00_photo.jpg")
            req_img = urllib.request.Request(images[0], headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req_img, timeout=20) as r_img:
                with open(target_path, "wb") as f_out:
                    f_out.write(r_img.read())
            downloaded = True

        if downloaded:
            return {"caption": caption}
    except Exception as e:
        print(f"opengraph scraper error: {e}")
    return {}

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

    # 1. First attempt: yt-dlp (fastest for reels and video posts)
    try:
        ytdl_res = _download_with_ytdlp(url, task_dir)
        caption = ytdl_res.get("caption", "")
        if ytdl_res.get("shortcode"):
            shortcode = ytdl_res["shortcode"]
    except Exception as e:
        print(f"yt-dlp attempt note: {e}")

    downloaded_files = get_valid_files()

    # 2. Second attempt: gallery-dl (photos, carousels, and stories with cookies)
    if not downloaded_files:
        gdl_res = _download_with_gallery_dl(url, task_dir)
        if not caption:
            caption = gdl_res.get("caption", "")
        downloaded_files = get_valid_files()

    # 3. Third attempt: OpenGraph scraper (bypasses login for single photo/video posts)
    if not downloaded_files:
        og_res = _download_with_opengraph(url, task_dir)
        if not caption:
            caption = og_res.get("caption", "")
        downloaded_files = get_valid_files()

    if not downloaded_files:
        raise ValueError(
            "اینستاگرام برای دانلود این پست یا استوری نیاز به لاگین دارد یا پیج خصوصی (Private) است."
        )

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
    """Run download in thread pool to prevent blocking the event loop."""
    return await asyncio.to_thread(_download_sync, url)

def cleanup_task_dir(task_dir: str):
    """Safely remove the temporary folder and its downloaded files."""
    try:
        if task_dir and os.path.exists(task_dir):
            shutil.rmtree(task_dir, ignore_errors=True)
    except Exception as e:
        print(f"Error cleaning task dir {task_dir}: {e}")
