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

def setup_ffmpeg():
    """Ensure ffmpeg is available in PATH."""
    if shutil.which("ffmpeg"):
        return
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        if ffmpeg_exe and os.path.exists(ffmpeg_exe):
            ffmpeg_dir = os.path.dirname(ffmpeg_exe)
            ffmpeg_link = os.path.join(ffmpeg_dir, "ffmpeg")
            if not os.path.exists(ffmpeg_link):
                try:
                    os.symlink(ffmpeg_exe, ffmpeg_link)
                except Exception:
                    pass
            current_path = os.environ.get("PATH", "")
            if ffmpeg_dir not in current_path:
                os.environ["PATH"] = ffmpeg_dir + os.pathsep + current_path
    except Exception as e:
        print(f"setup_ffmpeg error: {e}")

setup_ffmpeg()

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

YOUTUBE_REGEX = re.compile(
    r"(?:https?:\/\/)?(?:www\.|m\.)?(?:youtube\.com\/(?:watch\?v=|shorts\/|live\/|embed\/)|youtu\.be\/)([A-Za-z0-9_-]{11})",
    re.IGNORECASE
)

SPOTIFY_REGEX = re.compile(
    r"(?:https?:\/\/)?(?:open\.)?spotify\.com\/(?:track|album|playlist|intl-[a-z]+\/track)\/([A-Za-z0-9]+)",
    re.IGNORECASE
)

SOUNDCLOUD_REGEX = re.compile(
    r"(?:https?:\/\/)?(?:www\.|on\.)?soundcloud\.com\/\S+",
    re.IGNORECASE
)

TIKTOK_REGEX = re.compile(
    r"(?:https?:\/\/)?(?:www\.|vm\.|vt\.)?tiktok\.com\/\S+",
    re.IGNORECASE
)

TWITTER_REGEX = re.compile(
    r"(?:https?:\/\/)?(?:www\.)?(?:twitter\.com|x\.com)\/\S+\/status\/\d+",
    re.IGNORECASE
)

PINTEREST_REGEX = re.compile(
    r"(?:https?:\/\/)?(?:[a-z]{2}\.)?pinterest\.com\/\S+|pin\.it\/\S+",
    re.IGNORECASE
)

def detect_platform(url: str) -> str:
    if INSTA_URL_REGEX.search(url):
        return "instagram"
    if YOUTUBE_REGEX.search(url):
        return "youtube"
    if SPOTIFY_REGEX.search(url):
        return "spotify"
    if SOUNDCLOUD_REGEX.search(url):
        return "soundcloud"
    if TIKTOK_REGEX.search(url):
        return "tiktok"
    if TWITTER_REGEX.search(url):
        return "twitter"
    if PINTEREST_REGEX.search(url):
        return "pinterest"
    return "other"

def extract_shortcode(url: str) -> Optional[str]:
    match = INSTA_URL_REGEX.search(url)
    if match:
        return match.group(1)
    match_yt = YOUTUBE_REGEX.search(url)
    if match_yt:
        return match_yt.group(1)
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
        "format": "b/bestvideo[vcodec^=avc]+bestaudio[acodec^=mp4a]/bestvideo[vcodec^=avc]+bestaudio/best[vcodec^=avc]/best",
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
        "extract_flat": False,
        "retries": 2,
        "socket_timeout": 20,
    }

    try:
        import imageio_ffmpeg
        ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
        if ffmpeg_bin and os.path.exists(ffmpeg_bin):
            ydl_opts["ffmpeg_location"] = os.path.dirname(ffmpeg_bin)
    except Exception:
        pass

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

# ================= MULTI-PLATFORM DOWNLOADERS =================

def extract_youtube_info_sync(url: str) -> Dict[str, Any]:
    setup_ffmpeg()
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        video_id = info.get("id") or ""
        title = info.get("title") or "YouTube Video"
        duration = info.get("duration") or 0
        thumbnail = info.get("thumbnail") or ""
        channel = info.get("uploader") or info.get("channel") or ""

        heights = set()
        for f in info.get("formats", []):
            h = f.get("height")
            if h and f.get("vcodec") != "none":
                heights.add(h)

        common_resolutions = [1080, 720, 480, 360]
        available_res = [h for h in common_resolutions if any(vh >= h for vh in heights)]
        if not available_res and heights:
            available_res = sorted(list(heights), reverse=True)[:3]

        return {
            "id": video_id,
            "title": title,
            "duration": duration,
            "thumbnail": thumbnail,
            "channel": channel,
            "resolutions": available_res,
            "url": url,
        }

async def get_youtube_info(url: str) -> Dict[str, Any]:
    return await asyncio.to_thread(extract_youtube_info_sync, url)

def download_youtube_sync(video_id: str, quality: str) -> Dict[str, Any]:
    setup_ffmpeg()
    task_id = str(uuid.uuid4())
    task_dir = os.path.join(DOWNLOADS_DIR, task_id)
    os.makedirs(task_dir, exist_ok=True)

    url = f"https://www.youtube.com/watch?v={video_id}"
    outtmpl = os.path.join(task_dir, "%(title)s.%(ext)s")

    if quality == "audio":
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": outtmpl,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
            "quiet": True,
            "no_warnings": True,
        }
        media_type = "audio"
    else:
        q_int = int(quality) if quality.isdigit() else 720
        fmt = (
            f"bestvideo[height<={q_int}][vcodec^=avc]+bestaudio[acodec^=mp4a]/"
            f"bestvideo[height<={q_int}]+bestaudio/"
            f"best[height<={q_int}]/best"
        )
        ydl_opts = {
            "format": fmt,
            "outtmpl": outtmpl,
            "merge_output_format": "mp4",
            "quiet": True,
            "no_warnings": True,
        }
        media_type = "video"

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get("title") or "YouTube Video"
        duration = info.get("duration") or 0
        channel = info.get("uploader") or info.get("channel") or ""

    files = [
        f for f in glob.glob(os.path.join(task_dir, "*"))
        if os.path.isfile(f) and not f.endswith(".part") and not f.endswith(".ytdl")
    ]
    if not files:
        raise ValueError("دانلود فایل از یوتیوب ناموفق بود.")

    file_path = files[0]
    w, h, dur = get_media_dimensions(file_path)

    return {
        "task_dir": task_dir,
        "file_path": file_path,
        "type": media_type,
        "title": title,
        "artist": channel,
        "duration": dur or duration,
        "width": w,
        "height": h,
    }

async def download_youtube(video_id: str, quality: str) -> Dict[str, Any]:
    return await asyncio.to_thread(download_youtube_sync, video_id, quality)

def download_spotify_sync(url: str) -> Dict[str, Any]:
    setup_ffmpeg()
    task_id = str(uuid.uuid4())
    task_dir = os.path.join(DOWNLOADS_DIR, task_id)
    os.makedirs(task_dir, exist_ok=True)

    track_title = "Spotify Track"
    artist = ""

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        )
        with urllib.request.urlopen(req, timeout=12) as r:
            content = r.read().decode("utf-8", errors="ignore")
        m_title = re.search(r'<meta property="og:title" content="([^"]+)"', content)
        m_desc = re.search(r'<meta property="og:description" content="([^"]+)"', content)
        if m_title:
            track_title = html.unescape(m_title.group(1))
        if m_desc:
            desc_text = html.unescape(m_desc.group(1))
            artist = desc_text.split(" · ")[0] if " · " in desc_text else ""
    except Exception as e:
        print(f"Spotify meta fetch note: {e}")

    query = f"{artist} - {track_title} official audio" if artist else f"{track_title} audio"
    outtmpl = os.path.join(task_dir, f"{track_title}.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "320",
        }],
        "quiet": True,
        "no_warnings": True,
    }

    dur = 0
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"ytsearch1:{query}", download=True)
        entries = info.get("entries") or []
        if entries:
            dur = entries[0].get("duration") or 0

    files = [f for f in glob.glob(os.path.join(task_dir, "*")) if os.path.isfile(f) and f.endswith(".mp3")]
    if not files:
        raise ValueError("دانلود موزیک از اسپاتیفای با خطا مواجه شد.")

    return {
        "task_dir": task_dir,
        "file_path": files[0],
        "type": "audio",
        "title": track_title,
        "artist": artist,
        "duration": dur,
    }

async def download_spotify(url: str) -> Dict[str, Any]:
    return await asyncio.to_thread(download_spotify_sync, url)

def download_generic_sync(url: str, platform: str) -> Dict[str, Any]:
    setup_ffmpeg()
    task_id = str(uuid.uuid4())
    task_dir = os.path.join(DOWNLOADS_DIR, task_id)
    os.makedirs(task_dir, exist_ok=True)

    outtmpl = os.path.join(task_dir, "%(title)s.%(ext)s")

    if platform == "soundcloud":
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": outtmpl,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "256",
            }],
            "quiet": True,
            "no_warnings": True,
        }
        media_type = "audio"
    else:
        # TikTok, Twitter, Pinterest, etc.
        ydl_opts = {
            "format": "b/bestvideo[vcodec^=avc]+bestaudio/best",
            "outtmpl": outtmpl,
            "merge_output_format": "mp4",
            "quiet": True,
            "no_warnings": True,
        }
        media_type = "video"

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get("title") or info.get("description") or f"{platform.capitalize()} Media"
        duration = info.get("duration") or 0
        artist = info.get("uploader") or info.get("channel") or ""

    files = [
        f for f in glob.glob(os.path.join(task_dir, "*"))
        if os.path.isfile(f) and not f.endswith(".part") and not f.endswith(".ytdl")
    ]
    if not files:
        raise ValueError(f"دانلود محتوا از {platform} ناموفق بود.")

    file_path = files[0]
    w, h, dur = get_media_dimensions(file_path)

    ext = os.path.splitext(file_path)[1].lower()
    if ext in [".jpg", ".jpeg", ".png", ".webp"]:
        media_type = "photo"

    return {
        "task_dir": task_dir,
        "file_path": file_path,
        "type": media_type,
        "title": title,
        "artist": artist,
        "duration": dur or duration,
        "width": w,
        "height": h,
    }

async def download_generic(url: str, platform: str) -> Dict[str, Any]:
    return await asyncio.to_thread(download_generic_sync, url, platform)
