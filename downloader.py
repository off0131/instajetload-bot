import os
import shutil
import uuid
import asyncio
import re
import glob
import subprocess
import json
import urllib.request
import urllib.parse
import html
from typing import Optional, Dict, Any, List
import yt_dlp
from hachoir.parser import createParser
from hachoir.metadata import extractMetadata

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")
COOKIES_FILE = os.path.join(BASE_DIR, "cookies.txt")

os.makedirs(DOWNLOADS_DIR, exist_ok=True)

def ensure_cookies_file() -> Optional[str]:
    """Ensures cookies file is ready from Render Secret Files, Env Var, or local file."""
    render_secrets_path = "/etc/secrets/cookies.txt"
    if os.path.exists(render_secrets_path) and os.path.getsize(render_secrets_path) > 0:
        return render_secrets_path

    if os.path.exists(COOKIES_FILE) and os.path.getsize(COOKIES_FILE) > 0:
        return COOKIES_FILE

    env_cookies = os.environ.get("INSTAGRAM_COOKIES")
    if env_cookies and env_cookies.strip():
        try:
            content = env_cookies.strip()
            try:
                import base64
                decoded = base64.b64decode(content).decode("utf-8")
                if "instagram.com" in decoded or "Netscape" in decoded:
                    content = decoded
            except Exception:
                pass
            with open(COOKIES_FILE, "w", encoding="utf-8") as f:
                f.write(content)
            print("Successfully populated cookies.txt from INSTAGRAM_COOKIES env var.")
            return COOKIES_FILE
        except Exception as e:
            print(f"Error populating cookies.txt from env: {e}")

    return None

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

    cookies_path = ensure_cookies_file()
    if cookies_path:
        ydl_opts["cookiefile"] = cookies_path

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

    cookies_path = ensure_cookies_file()
    if cookies_path:
        cmd.extend(["--cookies", cookies_path])

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

def _download_via_embed_scraper(shortcode: str, url: str, task_dir: str) -> Dict[str, Any]:
    """Extracts direct mp4 video or full images by parsing Instagram embed endpoint without login."""
    caption = ""
    embed_url = f"https://www.instagram.com/p/{shortcode}/embed/captioned/"
    req = urllib.request.Request(
        embed_url,
        headers={
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read().decode("utf-8", errors="ignore")

        # 1. Extract caption if available
        caption_match = re.search(r'class="Caption"[^>]*>(.*?)</div>', content, re.DOTALL)
        if caption_match:
            raw_c = re.sub(r'<[^>]+>', '', caption_match.group(1))
            caption = html.unescape(raw_c).strip()

        # 2. Extract video URL if post is a video / reel
        m_video = re.search(r'video_url[\\\"\':\s]+(https:[^\\\"\']+\.mp4[^\\\"\']*)', content)
        if not m_video:
            # Secondary pattern
            m_video = re.search(r'\"video_url\":\s*\"(https:[^\"]+?\.mp4[^\"]*)\"', content.replace(r'\\\"', '"'))

        if m_video:
            raw_url = m_video.group(1)
            clean_url = (
                raw_url
                .replace('\\\\\\/', '/')
                .replace('\\\\/', '/')
                .replace('\\/', '/')
                .replace(r'\u0025', '%')
                .replace(r'\u0026', '&')
            )
            
            # Download video file
            video_req = urllib.request.Request(
                clean_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            with urllib.request.urlopen(video_req, timeout=40) as v_resp:
                v_data = v_resp.read()
                if len(v_data) > 10000:
                    v_path = os.path.join(task_dir, f"{shortcode}.mp4")
                    with open(v_path, "wb") as f_out:
                        f_out.write(v_data)
                    return {"caption": caption}
    except Exception as e:
        print(f"Embed scraper error for {shortcode}: {e}")

    return {"caption": caption}

def _download_uncropped_photo_and_caption(shortcode: str, url: str, task_dir: str) -> Dict[str, Any]:
    """Downloads original full-resolution uncropped photo (not the 640x640 square crop) and gets caption."""
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

    # 1. First attempt: yt-dlp (fastest for native streams)
    try:
        ytdl_res = _download_with_ytdlp(url, task_dir)
        caption = ytdl_res.get("caption", "")
        if ytdl_res.get("shortcode"):
            shortcode = ytdl_res["shortcode"]
    except Exception as e:
        print(f"yt-dlp attempt note: {e}")

    downloaded_files = get_valid_files()

    # 2. Second attempt: Instagram Embed Scraper (100% bypasses login for public reels and videos)
    if not downloaded_files and shortcode:
        try:
            embed_res = _download_via_embed_scraper(shortcode, url, task_dir)
            if not caption:
                caption = embed_res.get("caption", "")
            downloaded_files = get_valid_files()
        except Exception as e:
            print(f"embed attempt note: {e}")

    # 3. Third attempt: gallery-dl (multi-slide carousels and stories)
    if not downloaded_files:
        gdl_res = _download_with_gallery_dl(url, task_dir)
        if not caption:
            caption = gdl_res.get("caption", "")
        downloaded_files = get_valid_files()

    # 4. Fourth attempt: Uncropped full-resolution photo scraper
    if not downloaded_files and shortcode:
        if "/reel/" not in url.lower() and "/reels/" not in url.lower():
            photo_res = _download_uncropped_photo_and_caption(shortcode, url, task_dir)
            if not caption:
                caption = photo_res.get("caption", "")
            downloaded_files = get_valid_files()

    if not downloaded_files:
        raise ValueError(
            "اینستاگرام موقتاً اجازه دسترسی به این محتوا را نداد. در صورت تکرار، نیاز به ورود یا تنظیم کوکی است."
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
