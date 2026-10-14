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
from typing import Optional, Dict, Any, List, Union
import requests
import aiohttp
import yt_dlp
from hachoir.parser import createParser
from hachoir.metadata import extractMetadata
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC, ID3NoHeaderError

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")
COOKIES_FILE = os.path.join(BASE_DIR, "cookies.txt")

os.makedirs(DOWNLOADS_DIR, exist_ok=True)

def setup_ffmpeg():
    """Ensure ffmpeg is available in PATH or symlinked."""
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

def get_ffmpeg_dir() -> Optional[str]:
    """Returns the directory containing ffmpeg executable for yt-dlp."""
    setup_ffmpeg()
    w = shutil.which("ffmpeg")
    if w:
        return os.path.dirname(w)
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.exists(exe):
            return os.path.dirname(exe)
    except Exception:
        pass
    return None

def get_ffmpeg_bin() -> Optional[str]:
    """Returns the full path to ffmpeg executable."""
    setup_ffmpeg()
    w = shutil.which("ffmpeg")
    if w:
        return w
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.exists(exe):
            return exe
    except Exception:
        pass
    return None

def ensure_cookies_file() -> Optional[str]:
    """Ensures cookies file is ready from Render Secret Files, Env Var, or local file."""
    render_secrets_path = "/etc/secrets/cookies.txt"
    if os.path.exists(render_secrets_path) and os.path.getsize(render_secrets_path) > 0:
        return render_secrets_path

    env_cookies = os.environ.get("SESSION_COOKIES") or os.environ.get("YOUTUBE_COOKIES") or os.environ.get("INSTAGRAM_COOKIES")
    if env_cookies and env_cookies.strip():
        try:
            content = env_cookies.strip()
            try:
                import base64
                decoded = base64.b64decode(content).decode("utf-8")
                if "instagram.com" in decoded or "youtube.com" in decoded or "Netscape" in decoded:
                    content = decoded
            except Exception:
                pass
            with open(COOKIES_FILE, "w", encoding="utf-8") as f:
                f.write(content)
            print("Successfully populated cookies.txt from environment cookies.")
            return COOKIES_FILE
        except Exception as e:
            print(f"Error populating cookies.txt from env: {e}")

    if os.path.exists(COOKIES_FILE) and os.path.getsize(COOKIES_FILE) > 0:
        return COOKIES_FILE

    return None

def get_youtube_cookies_file() -> Optional[str]:
    """Returns cookies file if it contains valid YouTube cookies (login or visitor/preference tokens)."""
    for p in ["/etc/secrets/cookies.txt", COOKIES_FILE]:
        if os.path.exists(p) and os.path.getsize(p) > 50:
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    # Check for YouTube domain cookies or Netscape visitor/session cookie tokens
                    if ("youtube.com" in content or
                        re.search(r"(\t|\s)(LOGIN_INFO|__Secure-1PSID|__Secure-3PSID|__Secure-3PAPISID|__Secure-BUCKET|__Secure-YNID|SID|VISITOR_INFO1_LIVE|PREF|SOCS|YSC)(\t|\s)", content)):
                        return p
            except Exception:
                pass
    return None

INSTA_URL_REGEX = re.compile(
    r"(?:https?:\/\/)?(?:www\.)?(?:instagram\.com|instagr\.am)\/(?:p|reel|reels|tv|share\/(?:reel|p)|stories\/[^\/\s]+)\/([A-Za-z0-9_-]+)",
    re.IGNORECASE
)

def extract_youtube_id(url: str) -> Optional[str]:
    """Extract 11-character YouTube video ID from any format."""
    patterns = [
        r'(?:youtu\.be\/|v\/|vi\/|u\/\w\/|embed\/|shorts\/|live\/)([A-Za-z0-9_-]{11})',
        r'[?&]v=([A-Za-z0-9_-]{11})',
        r'youtube\.com\/watch\?(?:[^\s&]+&)*v=([A-Za-z0-9_-]{11})',
    ]
    for p in patterns:
        m = re.search(p, url, re.IGNORECASE)
        if m:
            return m.group(1)
    return None

def detect_platform(url: str) -> str:
    url_lower = url.lower()
    if "instagram.com" in url_lower or "instagr.am" in url_lower:
        return "instagram"
    if "youtube.com" in url_lower or "youtu.be" in url_lower:
        return "youtube"
    if "spotify.com" in url_lower or "spotify.link" in url_lower or "spotify.app.link" in url_lower:
        return "spotify"
    if "soundcloud.com" in url_lower:
        return "soundcloud"
    if "tiktok.com" in url_lower:
        return "tiktok"
    if "twitter.com" in url_lower or "x.com" in url_lower:
        return "twitter"
    if "pinterest.com" in url_lower or "pin.it" in url_lower:
        return "pinterest"
    return "other"

def extract_shortcode(url: str) -> Optional[str]:
    match = INSTA_URL_REGEX.search(url)
    if match:
        return match.group(1)
    yt_id = extract_youtube_id(url)
    if yt_id:
        return yt_id
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
    ff_dir = get_ffmpeg_dir()
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
    if ff_dir:
        ydl_opts["ffmpeg_location"] = ff_dir

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
                    c = meta.get("caption") or meta.get("description") or meta.get("title") or ""
                    if c and len(c) > len(caption):
                        caption = c
            except Exception:
                pass
        return {"caption": caption}
    except Exception as e:
        print(f"gallery-dl error: {e}")
        return {}

def _download_via_embed_scraper(shortcode: str, url: str, task_dir: str) -> Dict[str, Any]:
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

        caption_match = re.search(r'class="Caption"[^>]*>(.*?)</div>', content, re.DOTALL)
        if caption_match:
            import html as py_html
            raw_c = re.sub(r'<[^>]+>', '', caption_match.group(1))
            caption = py_html.unescape(raw_c).strip()

        m_video = re.search(r'video_url[\\\"\':\s]+(https:[^\\\"\']+\.mp4[^\\\"\']*)', content)
        if not m_video:
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
    if "/reel/" in url.lower() or "/reels/" in url.lower():
        return {}

    import html as py_html
    caption = ""
    try:
        clean_url = url.split("?")[0]
        req_og = urllib.request.Request(
            clean_url,
            headers={"User-Agent": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)"}
        )
        with urllib.request.urlopen(req_og, timeout=12) as r_og:
            page = r_og.read().decode("utf-8")
        descs = [py_html.unescape(m) for m in re.findall(r'property="og:description"\s+content="([^"]+)"', page)]
        if descs:
            caption = descs[0]
            if '": "' in caption:
                caption = caption.split('": "', 1)[1].rstrip('"\u200e .')
    except Exception as e:
        print(f"Caption fetch error: {e}")

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

RAPIDAPI_HOST = "instagram-downloader-download-instagram-stories-videos4.p.rapidapi.com"
DEFAULT_RAPIDAPI_KEYS = [
    "666b9e2849msh0fd5d0dae9f0734p15da1cjsnb87cf7ce902f"
]
_rapidapi_key_idx = 0

def get_rapidapi_keys() -> List[str]:
    raw = os.environ.get("RAPIDAPI_KEYS", "") or os.environ.get("RAPIDAPI_KEY", "")
    if raw.strip():
        keys = [k.strip() for k in raw.split(",") if k.strip()]
        if keys:
            return keys
    return list(DEFAULT_RAPIDAPI_KEYS)

def get_next_rapidapi_key() -> str:
    global _rapidapi_key_idx
    keys = get_rapidapi_keys()
    if not keys:
        return ""
    key = keys[_rapidapi_key_idx % len(keys)]
    _rapidapi_key_idx = (_rapidapi_key_idx + 1) % len(keys)
    return key

def _download_via_rapidapi(url: str, task_dir: str) -> Dict[str, Any]:
    """Downloads Instagram posts, reels, stories, or albums via RapidAPI key pool."""
    keys = get_rapidapi_keys()
    if not keys:
        return {}

    endpoint = f"https://{RAPIDAPI_HOST}/convert"
    
    # Try keys in rotation if one hits rate limits or quota
    for attempt in range(len(keys)):
        api_key = get_next_rapidapi_key()
        headers = {
            "x-rapidapi-key": api_key,
            "x-rapidapi-host": RAPIDAPI_HOST,
            "accept": "application/json"
        }
        params = {"url": url}
        
        try:
            resp = requests.get(endpoint, headers=headers, params=params, timeout=25)
            if resp.status_code == 429:
                print(f"[RapidAPI] Key {api_key[:6]}... rate-limited (429). Rotating...")
                continue
            if resp.status_code != 200:
                print(f"[RapidAPI] HTTP {resp.status_code}: {resp.text[:150]}")
                continue

            data = resp.json()
            if not isinstance(data, dict):
                continue
            if data.get("error"):
                print(f"[RapidAPI] Error response: {data.get('error')}")
                continue

            media_list = data.get("media") or []
            if not media_list and data.get("url"):
                media_list = [data]
            if not media_list:
                continue

            caption = data.get("title") or data.get("caption") or ""
            downloaded_count = 0

            for idx, item in enumerate(media_list):
                if not isinstance(item, dict):
                    continue
                file_url = item.get("url")
                if not file_url:
                    continue
                item_type = str(item.get("type", "")).lower()
                ext = ".mp4" if "video" in item_type else ".jpg"
                out_path = os.path.join(task_dir, f"media_{idx + 1:02d}{ext}")

                with requests.get(file_url, stream=True, timeout=30) as r:
                    r.raise_for_status()
                    with open(out_path, "wb") as f_out:
                        for chunk in r.iter_content(chunk_size=65536):
                            if chunk:
                                f_out.write(chunk)
                if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                    downloaded_count += 1

            if downloaded_count > 0:
                print(f"[RapidAPI] Successfully downloaded {downloaded_count} media files via key {api_key[:6]}...")
                return {"caption": caption, "source": "rapidapi"}

        except Exception as e:
            print(f"[RapidAPI] Request attempt exception: {e}")
            continue

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

    try:
        # 1. Primary attempt: RapidAPI (High-speed, unblocked, no cookies needed)
        try:
            rapid_res = _download_via_rapidapi(url, task_dir)
            if rapid_res:
                caption = rapid_res.get("caption", "")
        except Exception as e:
            print(f"RapidAPI attempt note: {e}")

        downloaded_files = get_valid_files()

        # 2. Second attempt: yt-dlp (Fallback)
        if not downloaded_files:
            try:
                ytdl_res = _download_with_ytdlp(url, task_dir)
                caption = ytdl_res.get("caption", "")
                if ytdl_res.get("shortcode"):
                    shortcode = ytdl_res["shortcode"]
            except Exception as e:
                print(f"yt-dlp attempt note: {e}")

            downloaded_files = get_valid_files()

        # 2. Second attempt: Instagram Embed Scraper
        if not downloaded_files and shortcode:
            try:
                embed_res = _download_via_embed_scraper(shortcode, url, task_dir)
                if not caption:
                    caption = embed_res.get("caption", "")
                downloaded_files = get_valid_files()
            except Exception as e:
                print(f"embed attempt note: {e}")

        # 3. Third attempt: gallery-dl
        if not downloaded_files:
            gdl_res = _download_with_gallery_dl(url, task_dir)
            if not caption:
                caption = gdl_res.get("caption", "")
            downloaded_files = get_valid_files()

        # 4. Fourth attempt: Uncropped photo scraper
        if not downloaded_files and shortcode:
            if "/reel/" not in url.lower() and "/reels/" not in url.lower():
                photo_res = _download_uncropped_photo_and_caption(shortcode, url, task_dir)
                if not caption:
                    caption = photo_res.get("caption", "")
                downloaded_files = get_valid_files()

        if not downloaded_files:
            raise ValueError("دانلود محتوا از اینستاگرام ناموفق بود.")

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
    except Exception:
        cleanup_task_dir(task_dir)
        raise

async def download_instagram_media(url: str) -> Dict[str, Any]:
    return await asyncio.to_thread(_download_sync, url)

def cleanup_task_dir(task_dir: str):
    """Safely remove the temporary folder and its downloaded files."""
    try:
        if task_dir and os.path.exists(task_dir):
            shutil.rmtree(task_dir, ignore_errors=True)
    except Exception as e:
        print(f"Error cleaning task dir {task_dir}: {e}")

# ================= MULTI-PLATFORM DOWNLOADERS =================

# YouTube client configurations to bypass datacenter IP blocks (e.g. Render, AWS, GCP)
YT_EXTRACTOR_ARGS = {
    "youtube": {
        "player_client": ["android"]
    }
}

def extract_youtube_info_sync(url: str) -> Dict[str, Any]:
    ff_dir = get_ffmpeg_dir()
    video_id = extract_youtube_id(url)
    clean_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else url
    proxy = os.environ.get("YOUTUBE_PROXY") or os.environ.get("HTTP_PROXY") or None
    yt_cookies = get_youtube_cookies_file()

    # Attempt 1: Modern visionos/web with Node.js JS runtime
    try:
        ydl_opts_1: Dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "nocheckcertificate": True,
            "socket_timeout": 20,
            "js_runtimes": {"node": {}},
        }
        if yt_cookies:
            ydl_opts_1["cookiefile"] = yt_cookies
        if ff_dir:
            ydl_opts_1["ffmpeg_location"] = ff_dir
        if proxy:
            ydl_opts_1["proxy"] = proxy

        with yt_dlp.YoutubeDL(ydl_opts_1) as ydl:
            info = ydl.extract_info(clean_url, download=False)
            vid = info.get("id") or video_id or ""
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
            if not available_res:
                available_res = [720, 480, 360]

            return {
                "id": vid,
                "title": title,
                "duration": duration,
                "thumbnail": thumbnail,
                "channel": channel,
                "resolutions": available_res,
                "url": clean_url,
            }
    except Exception as e_node:
        print(f"Visionos/Node extraction failed: {e_node}, attempting Android client...")

    # Attempt 2: Android client (works without JS runtime and bypasses datacenter web block)
    try:
        ydl_opts_android: Dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "nocheckcertificate": True,
            "socket_timeout": 20,
            "extractor_args": {"youtube": {"player_client": ["android"]}},
        }
        if ff_dir:
            ydl_opts_android["ffmpeg_location"] = ff_dir
        if proxy:
            ydl_opts_android["proxy"] = proxy

        with yt_dlp.YoutubeDL(ydl_opts_android) as ydl:
            info = ydl.extract_info(clean_url, download=False)
            vid = info.get("id") or video_id or ""
            title = info.get("title") or "YouTube Video"
            duration = info.get("duration") or 0
            thumbnail = info.get("thumbnail") or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
            channel = info.get("uploader") or info.get("channel") or ""
            return {
                "id": vid,
                "title": title,
                "duration": duration,
                "thumbnail": thumbnail,
                "channel": channel,
                "resolutions": [720, 480, 360],
                "url": clean_url,
            }
    except Exception as e_android:
        print(f"Android extraction failed: {e_android}, falling back to oEmbed...")

    # Attempt 3: Official YouTube oEmbed API (100% unblocked on all cloud/datacenter IPs)
    if video_id:
        try:
            oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
            r = requests.get(oembed_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
            if r.status_code == 200:
                data = r.json()
                return {
                    "id": video_id,
                    "title": data.get("title") or "YouTube Video",
                    "duration": 0,
                    "thumbnail": data.get("thumbnail_url") or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
                    "channel": data.get("author_name") or "YouTube",
                    "resolutions": [720, 480, 360],
                    "url": clean_url,
                }
        except Exception as e_oembed:
            print(f"oEmbed fallback error: {e_oembed}")

    raise ValueError("امکان دریافت اطلاعات ویدیو از یوتیوب وجود ندارد.")

extract_youtube_info = extract_youtube_info_sync

async def get_youtube_info(url: str) -> Dict[str, Any]:
    return await asyncio.to_thread(extract_youtube_info_sync, url)

async def download_youtube_via_helper(video_id: str, quality: str, task_dir: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Tier 3 Fallback: Downloads YouTube video/audio via external Loader.to REST helper API."""
    if not task_dir:
        task_id = str(uuid.uuid4())
        task_dir = os.path.join(DOWNLOADS_DIR, task_id)
        os.makedirs(task_dir, exist_ok=True)
        created_task_dir = True
    else:
        created_task_dir = False

    fmt = "mp3" if quality in ("audio", "mp3") else (quality if quality in ["360", "480", "720", "1080"] else "720")
    target_url = f"https://www.youtube.com/watch?v={video_id}"
    req_url = f"https://loader.to/ajax/download.php?button=1&start=1&end=1&format={fmt}&url={urllib.parse.quote(target_url, safe='')}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}

    success = False
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            progress_url = None
            raw_title = "YouTube Media"
            try:
                async with session.get(req_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("success"):
                            progress_url = data.get("progress_url")
                            raw_title = data.get("title") or "YouTube Media"
            except Exception as e:
                print(f"[Helper API] Init failed: {e}")
                return None

            if not progress_url:
                return None

            # Poll progress endpoint (up to 40 seconds)
            download_url = None
            for _ in range(20):
                await asyncio.sleep(2)
                try:
                    async with session.get(progress_url, timeout=aiohttp.ClientTimeout(total=8)) as p_resp:
                        if p_resp.status == 200:
                            p_data = await p_resp.json()
                            if p_data.get("success") == 1 and p_data.get("download_url"):
                                download_url = p_data.get("download_url")
                                if p_data.get("title"):
                                    raw_title = p_data.get("title")
                                break
                            elif p_data.get("success") == -1:
                                return None
                except Exception:
                    pass

            if not download_url:
                return None

            ext = "mp3" if quality in ("audio", "mp3") else "mp4"
            clean_name = re.sub(r'[\\/*?:"<>|]', "", raw_title)[:60].strip() or "video"
            out_file = os.path.join(task_dir, f"{clean_name}.{ext}")

            try:
                async with session.get(download_url, timeout=aiohttp.ClientTimeout(total=90)) as dl_resp:
                    if dl_resp.status != 200:
                        return None
                    with open(out_file, "wb") as f:
                        while chunk := await dl_resp.content.read(65536):
                            f.write(chunk)
            except Exception as e:
                print(f"[Helper API] Stream download failed: {e}")
                return None

            if os.path.exists(out_file) and os.path.getsize(out_file) > 1024:
                w, h, dur = get_media_dimensions(out_file)
                is_audio = quality in ("audio", "mp3")
                success = True
                return {
                    "task_dir": task_dir,
                    "file_path": out_file,
                    "type": "audio" if is_audio else "video",
                    "title": raw_title,
                    "artist": "YouTube",
                    "duration": dur or 0,
                    "width": w,
                    "height": h,
                    "thumbnail": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
                    "is_audio": is_audio,
                    "tier_used": 3,
                    "download_url": download_url,
                }
            return None
    finally:
        if not success and created_task_dir and task_dir and os.path.exists(task_dir):
            cleanup_task_dir(task_dir)

def download_youtube_via_helper_sync(video_id: str, quality: str, task_dir: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Synchronous Loader.to helper."""
    import time
    if not task_dir:
        task_id = str(uuid.uuid4())
        task_dir = os.path.join(DOWNLOADS_DIR, task_id)
        os.makedirs(task_dir, exist_ok=True)
        created_task_dir = True
    else:
        created_task_dir = False

    fmt = "mp3" if quality in ("audio", "mp3") else (quality if quality in ["360", "480", "720", "1080"] else "720")
    target_url = f"https://www.youtube.com/watch?v={video_id}"
    req_url = f"https://loader.to/ajax/download.php?button=1&start=1&end=1&format={fmt}&url={urllib.parse.quote(target_url, safe='')}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}

    success = False
    try:
        try:
            r = requests.get(req_url, headers=headers, timeout=10)
            if r.status_code != 200:
                return None
            data = r.json()
            if not data.get("success"):
                return None
            progress_url = data.get("progress_url")
            raw_title = data.get("title") or "YouTube Media"
        except Exception as e:
            print(f"[Helper API] Sync init failed: {e}")
            return None

        if not progress_url:
            return None

        download_url = None
        for _ in range(20):
            time.sleep(2)
            try:
                p_resp = requests.get(progress_url, headers=headers, timeout=8)
                if p_resp.status_code == 200:
                    p_data = p_resp.json()
                    if p_data.get("success") == 1 and p_data.get("download_url"):
                        download_url = p_data.get("download_url")
                        if p_data.get("title"):
                            raw_title = p_data.get("title")
                        break
                    elif p_data.get("success") == -1:
                        return None
            except Exception:
                pass

        if not download_url:
            return None

        ext = "mp3" if quality in ("audio", "mp3") else "mp4"
        clean_name = re.sub(r'[\\/*?:"<>|]', "", raw_title)[:60].strip() or "video"
        out_file = os.path.join(task_dir, f"{clean_name}.{ext}")

        try:
            with requests.get(download_url, headers=headers, stream=True, timeout=90) as stream_resp:
                if stream_resp.status_code != 200:
                    return None
                with open(out_file, "wb") as f:
                    for chunk in stream_resp.iter_content(chunk_size=65536):
                        if chunk:
                            f.write(chunk)
        except Exception as e:
            print(f"[Helper API] Sync stream download failed: {e}")
            return None

        if os.path.exists(out_file) and os.path.getsize(out_file) > 1024:
            w, h, dur = get_media_dimensions(out_file)
            is_audio = quality in ("audio", "mp3")
            success = True
            return {
                "task_dir": task_dir,
                "file_path": out_file,
                "type": "audio" if is_audio else "video",
                "title": raw_title,
                "artist": "YouTube",
                "duration": dur or 0,
                "width": w,
                "height": h,
                "thumbnail": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
                "is_audio": is_audio,
                "tier_used": 3,
                "download_url": download_url,
            }
        return None
    finally:
        if not success and created_task_dir and task_dir and os.path.exists(task_dir):
            cleanup_task_dir(task_dir)

def get_youtube_direct_cdn_url(video_id: str, quality: str) -> Optional[str]:
    """Fetch the high-speed direct CDN streaming URL from Loader.to / SaveNow REST API."""
    format_map = {
        "360": "360",
        "480": "480",
        "720": "720",
        "1080": "1080",
        "audio": "mp3",
        "mp3": "mp3"
    }
    fmt = format_map.get(str(quality), "720")
    start_url = (
        f"https://loader.to/ajax/download.php?button=1&start=1&end=1"
        f"&format={fmt}&url=https%3A%2F%2Fwww.youtube.com%2Fwatch%3Fv%3D{video_id}"
    )
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Referer": "https://en.loader.to/"
    }
    try:
        resp = requests.get(start_url, headers=headers, timeout=12)
        if resp.status_code != 200:
            return None
        data = resp.json()
        progress_url = data.get("progress_url")
        if not progress_url:
            return None
        for _ in range(15):
            time.sleep(2)
            try:
                p_resp = requests.get(progress_url, headers=headers, timeout=8)
                if p_resp.status_code == 200:
                    p_data = p_resp.json()
                    if p_data.get("download_url"):
                        return p_data.get("download_url")
                    elif p_data.get("success") == -1:
                        return None
            except Exception:
                pass
    except Exception as e:
        print(f"[CDN Direct URL] Error: {e}")
    return None

def download_youtube_sync(video_id: str, quality: str, task_dir: Optional[str] = None) -> Dict[str, Any]:
    ff_dir = get_ffmpeg_dir()
    if not task_dir:
        task_id = str(uuid.uuid4())
        task_dir = os.path.join(DOWNLOADS_DIR, task_id)
        os.makedirs(task_dir, exist_ok=True)
        created_task_dir = True
    else:
        created_task_dir = False

    success = False
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        outtmpl = os.path.join(task_dir, "%(title)s.%(ext)s")
        proxy = os.environ.get("YOUTUBE_PROXY") or os.environ.get("HTTP_PROXY") or None
        yt_cookies = get_youtube_cookies_file()

        is_audio = quality in ("audio", "mp3")
        media_type = "audio" if is_audio else "video"
        q_int = int(quality) if quality.isdigit() else 720

        downloaded = False
        title = "YouTube Video"
        duration = 0
        channel = ""
        tier_used = 0

        # Tier 1: High-resolution download via visionos/web with Node.js JS solver
        try:
            if is_audio:
                ydl_opts_1 = {
                    "format": "ba/b",
                    "outtmpl": outtmpl,
                    "postprocessors": [{
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }],
                    "retries": 5,
                    "fragment_retries": 5,
                    "quiet": True,
                    "no_warnings": True,
                    "nocheckcertificate": True,
                    "socket_timeout": 35,
                    "js_runtimes": {"node": {}},
                }
            else:
                fmt_1 = (
                    f"bv*[height<={q_int}][ext=mp4]+ba[ext=m4a]/"
                    f"bv*[height<={q_int}]+ba/"
                    f"b[height<={q_int}][ext=mp4]/"
                    f"b[height<={q_int}]/"
                    f"bestvideo[height<={q_int}]+bestaudio/"
                    f"best[height<={q_int}]/"
                    f"18/best"
                )
                ydl_opts_1 = {
                    "format": fmt_1,
                    "outtmpl": outtmpl,
                    "merge_output_format": "mp4",
                    "postprocessor_args": {"Merger": ["-c:v", "copy", "-c:a", "aac"]},
                    "retries": 5,
                    "fragment_retries": 5,
                    "quiet": True,
                    "no_warnings": True,
                    "nocheckcertificate": True,
                    "socket_timeout": 35,
                    "js_runtimes": {"node": {}},
                }

            if yt_cookies:
                ydl_opts_1["cookiefile"] = yt_cookies
            if ff_dir:
                ydl_opts_1["ffmpeg_location"] = ff_dir
            if proxy:
                ydl_opts_1["proxy"] = proxy

            with yt_dlp.YoutubeDL(ydl_opts_1) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get("title") or title
                duration = info.get("duration") or 0
                channel = info.get("uploader") or info.get("channel") or ""
                downloaded = True
                tier_used = 1
        except Exception as e1:
            print(f"[YouTube DL] Strategy 1 (visionos/node) note: {e1}, failing over to Strategy 2 (android)...")

        # Tier 2: Bulletproof Android client DASH (bypasses datacenter web bot guard)
        if not downloaded:
            try:
                if is_audio:
                    ydl_opts_2 = {
                        "format": "ba/b/18/best",
                        "outtmpl": outtmpl,
                        "postprocessors": [{
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                            "preferredquality": "192",
                        }],
                        "retries": 5,
                        "fragment_retries": 5,
                        "quiet": True,
                        "no_warnings": True,
                        "nocheckcertificate": True,
                        "socket_timeout": 35,
                        "extractor_args": {"youtube": {"player_client": ["android"]}},
                    }
                else:
                    ydl_opts_2 = {
                        "format": f"bv*[height<={q_int}]+ba/b[height<={q_int}]/18/best",
                        "outtmpl": outtmpl,
                        "merge_output_format": "mp4",
                        "retries": 5,
                        "fragment_retries": 5,
                        "quiet": True,
                        "no_warnings": True,
                        "nocheckcertificate": True,
                        "socket_timeout": 35,
                        "extractor_args": {"youtube": {"player_client": ["android"]}},
                    }
                if ff_dir:
                    ydl_opts_2["ffmpeg_location"] = ff_dir
                if proxy:
                    ydl_opts_2["proxy"] = proxy

                with yt_dlp.YoutubeDL(ydl_opts_2) as ydl:
                    info = ydl.extract_info(url, download=True)
                    title = info.get("title") or title
                    duration = info.get("duration") or duration
                    channel = info.get("uploader") or info.get("channel") or channel
                    downloaded = True
                    tier_used = 2
            except Exception as e2:
                print(f"[YouTube DL] Strategy 2 (android) error: {e2}")

        files = [
            f for f in glob.glob(os.path.join(task_dir, "*"))
            if os.path.isfile(f) and not f.endswith(".part") and not f.endswith(".ytdl")
        ]
        if not files:
            # Tier 3 Fallback: Unblocked external Loader.to / SaveNow REST helper
            print(f"[YouTube DL] Local strategies 1 & 2 failed or blocked on datacenter IP. Calling Tier 3 (External Helper)...")
            try:
                helper_res = download_youtube_via_helper_sync(video_id, quality, task_dir=task_dir)
                if helper_res and helper_res.get("file_path") and os.path.exists(helper_res["file_path"]):
                    success = True
                    return helper_res
            except Exception as e3:
                print(f"[YouTube DL] Tier 3 helper error: {e3}")

        files = [
            f for f in glob.glob(os.path.join(task_dir, "*"))
            if os.path.isfile(f) and not f.endswith(".part") and not f.endswith(".ytdl")
        ]
        if not files:
            raise ValueError("دانلود فایل از یوتیوب ناموفق بود.")

        file_path = files[0]
        w, h, dur = get_media_dimensions(file_path)

        success = True
        return {
            "task_dir": task_dir,
            "file_path": file_path,
            "type": media_type,
            "title": title,
            "artist": channel,
            "duration": dur or duration,
            "width": w,
            "height": h,
            "thumbnail": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
            "is_audio": is_audio,
            "tier_used": tier_used,
        }
    finally:
        if not success and created_task_dir and task_dir and os.path.exists(task_dir):
            cleanup_task_dir(task_dir)

async def download_youtube(video_id: str, quality: str) -> Dict[str, Any]:
    """Downloads YouTube media using 3-tier fallback architecture:
    Tier 1 (Node/web) -> Tier 2 (Android DASH) -> Tier 3 (External Loader.to helper).
    """
    # 1. Attempt Tier 1 & Tier 2 native yt-dlp in thread
    try:
        res = await asyncio.to_thread(download_youtube_sync, video_id, quality)
        if res and os.path.exists(res.get("file_path", "")):
            return res
    except Exception as e_ytdlp:
        print(f"[YouTube DL] yt-dlp pipeline failed ({e_ytdlp}), falling over to Tier 3 helper...")

    # 2. Attempt Tier 3: External Loader.to helper
    task_id = str(uuid.uuid4())
    task_dir = os.path.join(DOWNLOADS_DIR, task_id)
    os.makedirs(task_dir, exist_ok=True)
    success = False
    try:
        res_ext = await download_youtube_via_helper(video_id, quality, task_dir)
        if res_ext and os.path.exists(res_ext.get("file_path", "")):
            success = True
            return res_ext
    except Exception as e_helper:
        print(f"[YouTube DL] External helper error: {e_helper}")
    finally:
        if not success and os.path.exists(task_dir):
            cleanup_task_dir(task_dir)

    raise ValueError("دانلود فایل از یوتیوب ناموفق بود.")

SPOTIFY_URL_REGEX = re.compile(
    r"(?:https?:\/\/)?(?:open\.)?spotify\.(?:com|link|app\.link)\/(?:intl-[a-z]{2}\/)?(track|album|playlist|episode)\/([A-Za-z0-9]{22})",
    re.IGNORECASE
)

def unshorten_spotify_url(url: str) -> str:
    """Follow redirects for spotify.link or spotify.app.link shortened URLs."""
    if "spotify.link" in url or "spotify.app.link" in url:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                return resp.geturl()
        except Exception:
            pass
    return url

def embed_id3_tags(mp3_path: str, title: str, artist: str = "", album: str = "", cover_bytes: Optional[bytes] = None):
    """Embeds accurate ID3v2.3 tags into the output MP3 file using mutagen."""
    try:
        try:
            audio = MP3(mp3_path, ID3=ID3)
        except ID3NoHeaderError:
            audio = MP3(mp3_path)
            audio.add_tags()

        if title:
            audio.tags.add(TIT2(encoding=3, text=title))
        if artist:
            audio.tags.add(TPE1(encoding=3, text=artist))
        if album:
            audio.tags.add(TALB(encoding=3, text=album))
        if cover_bytes:
            audio.tags.add(APIC(
                encoding=3,
                mime="image/jpeg",
                type=3,
                desc="Cover",
                data=cover_bytes
            ))
        audio.save(v2_version=3)
    except Exception as e:
        print(f"Error embedding ID3 tags into {mp3_path}: {e}")

def parse_spotify_html(html_text: str, default_type: str = "track") -> Dict[str, Any]:
    """Parses Spotify metadata from embed __NEXT_DATA__ JSON or OpenGraph meta tags."""
    # 1. Tier 1: Next.js embed __NEXT_DATA__
    m_next = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html_text)
    if m_next:
        try:
            data = json.loads(m_next.group(1))
            entity = data.get("props", {}).get("pageProps", {}).get("state", {}).get("data", {}).get("entity", {})
            if entity:
                images = entity.get("visualIdentity", {}).get("image", [])
                cover_url = images[-1].get("url") if images else None
                e_type = (entity.get("type") or default_type).lower()
                if e_type in ("album", "playlist") or "trackList" in entity:
                    title = entity.get("title") or entity.get("name") or "Spotify Album"
                    artist_str = entity.get("subtitle") or ""
                    tracks = []
                    for t in entity.get("trackList", []):
                        uri = t.get("uri", "")
                        tid = uri.split(":")[-1] if ":" in uri else ""
                        dur_sec = (t.get("duration") or 0) // 1000
                        tracks.append({
                            "id": tid,
                            "title": t.get("title", ""),
                            "artist": t.get("subtitle") or artist_str,
                            "duration": dur_sec,
                            "album": title,
                            "cover_url": cover_url,
                            "url": f"https://open.spotify.com/track/{tid}" if tid else "",
                        })
                    return {
                        "type": "album" if e_type == "album" else "playlist",
                        "title": title,
                        "artist": artist_str,
                        "album": title,
                        "cover_url": cover_url,
                        "track_count": len(tracks),
                        "tracks": tracks,
                    }
                else:
                    artists = [a.get("name") for a in entity.get("artists", []) if a.get("name")]
                    artist_str = ", ".join(artists) if artists else entity.get("subtitle", "")
                    title = entity.get("title") or entity.get("name") or "Spotify Track"
                    dur_sec = (entity.get("duration") or 0) // 1000
                    return {
                        "type": "track",
                        "title": title,
                        "artist": artist_str,
                        "album": entity.get("album", {}).get("name") or "",
                        "duration": dur_sec,
                        "cover_url": cover_url,
                        "tracks": None,
                    }
        except Exception as e:
            print(f"Error parsing __NEXT_DATA__: {e}")

    # 2. Tier 2: OpenGraph social meta tags
    import html as py_html
    track_title = "Spotify Track"
    artist = ""
    cover_url = None

    m_title = re.search(r'<meta property="og:title" content="([^"]+)"', html_text)
    m_desc = re.search(r'<meta property="og:description" content="([^"]+)"', html_text)
    m_img = re.search(r'<meta property="og:image" content="([^"]+)"', html_text)

    if m_img:
        cover_url = py_html.unescape(m_img.group(1))

    if m_title:
        raw_title = py_html.unescape(m_title.group(1))
        if " | Spotify" in raw_title:
            raw_title = raw_title.replace(" | Spotify", "")
        if " - Single by " in raw_title:
            parts = raw_title.split(" - Single by ")
            track_title = parts[0].strip()
            if not artist and len(parts) > 1:
                artist = parts[1].strip()
        elif " - song by " in raw_title:
            parts = raw_title.split(" - song by ")
            track_title = parts[0].strip()
            if not artist and len(parts) > 1:
                artist = parts[1].strip()
        elif " - song and lyrics by " in raw_title:
            parts = raw_title.split(" - song and lyrics by ")
            track_title = parts[0].strip()
            if not artist and len(parts) > 1:
                artist = parts[1].strip()
        else:
            track_title = raw_title

    if m_desc and not artist:
        desc_text = py_html.unescape(m_desc.group(1))
        artist = desc_text.split(" · ")[0] if " · " in desc_text else ""

    return {
        "type": default_type,
        "title": track_title,
        "artist": artist,
        "album": "",
        "duration": 0,
        "cover_url": cover_url,
        "tracks": None,
    }

def extract_spotify_info(url: str) -> Optional[Dict[str, Any]]:
    """Resolves Spotify metadata for tracks and albums using 100% free embed Next.js state + fallback.
    Returns: {"type": "track"|"album", "title": str, "artist": str, "cover_url": Optional[str], "tracks": Optional[List[Dict[str, Any]]], "duration": int, "album": str}
    """
    canonical_url = unshorten_spotify_url(url)
    m = SPOTIFY_URL_REGEX.search(canonical_url)
    entity_type = "track"
    entity_id = ""
    embed_url = canonical_url

    if m:
        entity_type = m.group(1).lower()
        entity_id = m.group(2)
        embed_url = f"https://open.spotify.com/embed/{entity_type}/{entity_id}"

    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}

    try:
        req = urllib.request.Request(embed_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        res = parse_spotify_html(html, default_type=entity_type)
        if entity_id and "id" not in res:
            res["id"] = entity_id
        return res
    except Exception as e:
        print(f"Spotify embed metadata fetch note: {e}")

    if embed_url != canonical_url:
        try:
            req = urllib.request.Request(canonical_url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            res = parse_spotify_html(html, default_type=entity_type)
            if entity_id and "id" not in res:
                res["id"] = entity_id
            return res
        except Exception as e2:
            print(f"Spotify direct metadata fallback note: {e2}")

    return None

async def get_spotify_info(url: str) -> Optional[Dict[str, Any]]:
    return await asyncio.to_thread(extract_spotify_info, url)

def download_spotify_sync(url_or_track_dict: Union[str, Dict[str, Any]], task_dir: Optional[str] = None) -> Dict[str, Any]:
    ff_dir = get_ffmpeg_dir()
    if not task_dir:
        task_id = str(uuid.uuid4())
        task_dir = os.path.join(DOWNLOADS_DIR, task_id)
        os.makedirs(task_dir, exist_ok=True)
        created_task_dir = True
    else:
        created_task_dir = False

    success = False
    try:
        proxy = os.environ.get("YOUTUBE_PROXY") or os.environ.get("HTTP_PROXY") or None

        track_title = "Spotify Track"
        artist = ""
        album = ""
        cover_url = None
        spotify_dur = 0

        if isinstance(url_or_track_dict, dict):
            track_title = url_or_track_dict.get("title") or track_title
            artist = url_or_track_dict.get("artist") or ""
            album = url_or_track_dict.get("album") or ""
            cover_url = url_or_track_dict.get("cover_url")
            spotify_dur = url_or_track_dict.get("duration") or 0
        else:
            url = str(url_or_track_dict)
            # Scrape metadata via embed or direct page
            try:
                headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=12) as r:
                    content = r.read().decode("utf-8", errors="ignore")
                meta = parse_spotify_html(content)
                track_title = meta.get("title") or track_title
                artist = meta.get("artist") or ""
                album = meta.get("album") or ""
                cover_url = meta.get("cover_url")
                spotify_dur = meta.get("duration") or 0
            except Exception as e:
                print(f"Spotify meta fetch note: {e}")

        clean_artist = artist.strip()
        clean_title = re.sub(r'\(Remastered.*?\)|\[Explicit\]|\(feat\..*?\)', '', track_title, flags=re.IGNORECASE).strip()
        query = f"{clean_artist} - {clean_title}" if clean_artist else track_title
        outtmpl = os.path.join(task_dir, "%(title)s.%(ext)s")

        dur = 0
        downloaded = False

        # 1. Search SoundCloud first (standard streaming audio bestaudio/best, no login required)
        try:
            sc_opts = {
                "format": "bestaudio/best",
                "outtmpl": outtmpl,
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "320",
                }],
                "retries": 3,
                "quiet": True,
                "no_warnings": True,
                "nocheckcertificate": True,
                "socket_timeout": 20,
            }
            if ff_dir:
                sc_opts["ffmpeg_location"] = ff_dir
            if proxy:
                sc_opts["proxy"] = proxy

            with yt_dlp.YoutubeDL(sc_opts) as ydl:
                info = ydl.extract_info(f"scsearch1:{query}", download=True)
                entries = info.get("entries") or []
                if entries:
                    dur = entries[0].get("duration") or 0
                    downloaded = True
        except Exception as e_sc:
            print(f"SoundCloud search fallback: {e_sc}")

        # 2. Fallback to YouTube with Android client (unblocked on datacenter IPs)
        if not downloaded:
            queries_to_try = [f"{query} audio", f"{query} official audio", query]
            for q in queries_to_try:
                try:
                    yt_opts = {
                        "format": "18/best/ba",
                        "outtmpl": outtmpl,
                        "postprocessors": [{
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                            "preferredquality": "320",
                        }],
                        "retries": 3,
                        "quiet": True,
                        "no_warnings": True,
                        "nocheckcertificate": True,
                        "socket_timeout": 30,
                        "extractor_args": {"youtube": {"player_client": ["android"]}},
                    }
                    if ff_dir:
                        yt_opts["ffmpeg_location"] = ff_dir
                    if proxy:
                        yt_opts["proxy"] = proxy

                    with yt_dlp.YoutubeDL(yt_opts) as ydl:
                        info = ydl.extract_info(f"ytsearch1:{q}", download=True)
                        entries = info.get("entries") or []
                        if entries:
                            dur = entries[0].get("duration") or 0
                            downloaded = True
                            break
                except Exception as e_yt:
                    print(f"YouTube search fallback for '{q}': {e_yt}")

        files = [f for f in glob.glob(os.path.join(task_dir, "*")) if os.path.isfile(f) and f.endswith(".mp3")]
        if not files:
            all_downloaded = [
                f for f in glob.glob(os.path.join(task_dir, "*"))
                if os.path.isfile(f) and not f.endswith(".part") and not f.endswith(".ytdl")
            ]
            if all_downloaded:
                raw_f = all_downloaded[0]
                target_mp3 = os.path.join(task_dir, f"{track_title}.mp3")
                ffmpeg_exe = get_ffmpeg_bin() or "ffmpeg"
                try:
                    subprocess.run(
                        [ffmpeg_exe, "-y", "-i", raw_f, "-vn", "-b:a", "320k", target_mp3],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=True
                    )
                    if os.path.exists(target_mp3):
                        files = [target_mp3]
                except Exception as e_ff:
                    print(f"Manual FFmpeg convert error: {e_ff}")

        if not files:
            raise ValueError("دانلود موزیک از اسپاتیفای با خطا مواجه شد.")

        mp3_file = files[0]

        # Embed high-res cover art and ID3 metadata via Mutagen
        cover_path = None
        cover_bytes = None
        if cover_url:
            try:
                c_req = urllib.request.Request(cover_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(c_req, timeout=8) as c_resp:
                    cover_bytes = c_resp.read()
                if cover_bytes:
                    cover_path = os.path.join(task_dir, "cover.jpg")
                    with open(cover_path, "wb") as cf:
                        cf.write(cover_bytes)
            except Exception as e_cov:
                print(f"Cover download error: {e_cov}")

        embed_id3_tags(mp3_file, title=track_title, artist=artist, album=album, cover_bytes=cover_bytes)

        success = True
        return {
            "task_dir": task_dir,
            "file_path": mp3_file,
            "type": "audio",
            "title": track_title,
            "artist": artist,
            "album": album,
            "duration": dur or spotify_dur,
            "cover_path": cover_path if (cover_bytes and cover_path and os.path.exists(cover_path)) else None,
            "bitrate": "320k",
        }
    finally:
        if not success and created_task_dir and task_dir and os.path.exists(task_dir):
            cleanup_task_dir(task_dir)

async def download_spotify(url_or_track_dict: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
    return await asyncio.to_thread(download_spotify_sync, url_or_track_dict)

async def download_spotify_album(url: str, max_tracks: int = 25) -> List[Dict[str, Any]]:
    """Sequential album downloader supporting up to max_tracks tracks."""
    info = await asyncio.to_thread(extract_spotify_info, url)
    if not info or not info.get("tracks"):
        raise ValueError("اطلاعات آلبوم اسپاتیفای یافت نشد.")

    results = []
    tracks = info["tracks"][:max_tracks]
    for track in tracks:
        res = await download_spotify(track)
        results.append(res)
        await asyncio.sleep(0.5)
    return results

def download_twitter_sync(url: str) -> Dict[str, Any]:
    """Downloads Twitter/X media via FxTwitter API, gallery-dl, or yt-dlp."""
    task_id = str(uuid.uuid4())
    task_dir = os.path.join(DOWNLOADS_DIR, task_id)
    os.makedirs(task_dir, exist_ok=True)
    success = False
    try:
        title = "Twitter Post"
        artist = ""

        # 1. Tier 1: FxTwitter API
        m = re.search(r'status/(\d+)', url)
        if m:
            status_id = m.group(1)
            api_url = f"https://api.fxtwitter.com/i/status/{status_id}"
            try:
                req = urllib.request.Request(
                    api_url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                )
                with urllib.request.urlopen(req, timeout=12) as resp:
                    data = json.loads(resp.read().decode())

                tweet = data.get("tweet", {})
                title = tweet.get("text") or "Twitter Post"
                author = tweet.get("author", {})
                artist = author.get("name") or author.get("screen_name") or ""
                media = tweet.get("media", {})

                videos = media.get("videos") or []
                photos = media.get("photos") or []

                if videos:
                    vid_url = videos[0].get("url")
                    if vid_url:
                        out_path = os.path.join(task_dir, f"{status_id}.mp4")
                        v_req = urllib.request.Request(vid_url, headers={"User-Agent": "Mozilla/5.0"})
                        with urllib.request.urlopen(v_req, timeout=35) as v_resp:
                            with open(out_path, "wb") as f_out:
                                f_out.write(v_resp.read())
                        w, h, dur = get_media_dimensions(out_path)
                        success = True
                        return {
                            "task_dir": task_dir,
                            "file_path": out_path,
                            "type": "video",
                            "title": title,
                            "artist": artist,
                            "duration": dur,
                            "width": w,
                            "height": h,
                        }

                if photos:
                    photo_url = photos[0].get("url")
                    if photo_url:
                        ext = ".jpg"
                        if ".png" in photo_url.lower():
                            ext = ".png"
                        out_path = os.path.join(task_dir, f"{status_id}{ext}")
                        p_req = urllib.request.Request(photo_url, headers={"User-Agent": "Mozilla/5.0"})
                        with urllib.request.urlopen(p_req, timeout=20) as p_resp:
                            with open(out_path, "wb") as f_out:
                                f_out.write(p_resp.read())
                        w, h, dur = get_media_dimensions(out_path)
                        success = True
                        return {
                            "task_dir": task_dir,
                            "file_path": out_path,
                            "type": "photo",
                            "title": title,
                            "artist": artist,
                            "duration": dur,
                            "width": w,
                            "height": h,
                        }
            except Exception as e:
                print(f"FxTwitter API attempt note: {e}")

        # 2. Tier 2: gallery-dl
        try:
            _download_with_gallery_dl(url, task_dir)
            files = [
                f for f in glob.glob(os.path.join(task_dir, "**", "*"), recursive=True)
                if os.path.isfile(f) and not f.endswith(".json") and not f.endswith(".part")
            ]
            if files:
                file_path = files[0]
                ext = os.path.splitext(file_path)[1].lower()
                m_type = "video" if ext in [".mp4", ".mov", ".webm"] else "photo"
                w, h, dur = get_media_dimensions(file_path)
                success = True
                return {
                    "task_dir": task_dir,
                    "file_path": file_path,
                    "type": m_type,
                    "title": title,
                    "artist": artist,
                    "duration": dur,
                    "width": w,
                    "height": h,
                }
        except Exception as e:
            print(f"gallery-dl twitter note: {e}")

        # 3. Tier 3: yt-dlp
        ff_dir = get_ffmpeg_dir()
        outtmpl = os.path.join(task_dir, "%(title)s.%(ext)s")
        ydl_opts: Dict[str, Any] = {
            "format": "best[ext=mp4]/bestvideo+bestaudio/best",
            "outtmpl": outtmpl,
            "merge_output_format": "mp4",
            "quiet": True,
            "no_warnings": True,
        }
        if ff_dir:
            ydl_opts["ffmpeg_location"] = ff_dir

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title") or info.get("description") or title
            artist = info.get("uploader") or artist

        files = [f for f in glob.glob(os.path.join(task_dir, "*")) if os.path.isfile(f)]
        if not files:
            raise ValueError("دانلود محتوا از توییتر ناموفق بود.")

        file_path = files[0]
        ext = os.path.splitext(file_path)[1].lower()
        m_type = "video" if ext in [".mp4", ".mov", ".webm"] else "photo"
        w, h, dur = get_media_dimensions(file_path)

        success = True
        return {
            "task_dir": task_dir,
            "file_path": file_path,
            "type": m_type,
            "title": title,
            "artist": artist,
            "duration": dur,
            "width": w,
            "height": h,
        }
    finally:
        if not success and task_dir and os.path.exists(task_dir):
            cleanup_task_dir(task_dir)

def download_pinterest_sync(url: str) -> Dict[str, Any]:
    """Downloads Pinterest pin images and videos via RapidAPI, gallery-dl or yt-dlp."""
    task_id = str(uuid.uuid4())
    task_dir = os.path.join(DOWNLOADS_DIR, task_id)
    os.makedirs(task_dir, exist_ok=True)
    success = False
    try:
        title = "Pinterest Pin"

        # 1. Tier 1: RapidAPI
        try:
            r_res = _download_via_rapidapi(url, task_dir)
            if r_res.get("caption"):
                title = r_res["caption"]
            files = [
                f for f in glob.glob(os.path.join(task_dir, "**", "*"), recursive=True)
                if os.path.isfile(f) and not f.endswith(".json") and not f.endswith(".part")
            ]
            if files:
                file_path = files[0]
                ext = os.path.splitext(file_path)[1].lower()
                m_type = "video" if ext in [".mp4", ".mov", ".webm"] else "photo"
                w, h, dur = get_media_dimensions(file_path)
                success = True
                return {
                    "task_dir": task_dir,
                    "file_path": file_path,
                    "type": m_type,
                    "title": title,
                    "artist": "Pinterest",
                    "duration": dur,
                    "width": w,
                    "height": h,
                }
        except Exception as e:
            print(f"Pinterest RapidAPI note: {e}")

        # 2. Tier 2: gallery-dl (handles both images and videos)
        try:
            res = _download_with_gallery_dl(url, task_dir)
            if res.get("caption"):
                title = res["caption"]
            files = [
                f for f in glob.glob(os.path.join(task_dir, "**", "*"), recursive=True)
                if os.path.isfile(f) and not f.endswith(".json") and not f.endswith(".part")
            ]
            if files:
                file_path = files[0]
                ext = os.path.splitext(file_path)[1].lower()
                m_type = "video" if ext in [".mp4", ".mov", ".webm"] else "photo"
                w, h, dur = get_media_dimensions(file_path)
                success = True
                return {
                    "task_dir": task_dir,
                    "file_path": file_path,
                    "type": m_type,
                    "title": title,
                    "artist": "Pinterest",
                    "duration": dur,
                    "width": w,
                    "height": h,
                }
        except Exception as e:
            print(f"Pinterest gallery-dl note: {e}")

        # 2. Tier 2: yt-dlp (for video pins)
        ff_dir = get_ffmpeg_dir()
        outtmpl = os.path.join(task_dir, "%(title)s.%(ext)s")
        ydl_opts: Dict[str, Any] = {
            "format": "best[ext=mp4]/best",
            "outtmpl": outtmpl,
            "quiet": True,
            "no_warnings": True,
        }
        if ff_dir:
            ydl_opts["ffmpeg_location"] = ff_dir

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get("title") or title
            files = [f for f in glob.glob(os.path.join(task_dir, "*")) if os.path.isfile(f)]
            if files:
                file_path = files[0]
                ext = os.path.splitext(file_path)[1].lower()
                m_type = "video" if ext in [".mp4", ".mov", ".webm"] else "photo"
                w, h, dur = get_media_dimensions(file_path)
                success = True
                return {
                    "task_dir": task_dir,
                    "file_path": file_path,
                    "type": m_type,
                    "title": title,
                    "artist": "Pinterest",
                    "duration": dur,
                    "width": w,
                    "height": h,
                }
        except Exception as e:
            print(f"Pinterest yt-dlp note: {e}")

        raise ValueError("دانلود محتوا از پینترست ناموفق بود.")
    finally:
        if not success and task_dir and os.path.exists(task_dir):
            cleanup_task_dir(task_dir)

def download_generic_sync(url: str, platform: str) -> Dict[str, Any]:
    if platform == "twitter":
        return download_twitter_sync(url)
    if platform == "pinterest":
        return download_pinterest_sync(url)

    setup_ffmpeg()
    ff_dir = get_ffmpeg_dir()
    task_id = str(uuid.uuid4())
    task_dir = os.path.join(DOWNLOADS_DIR, task_id)
    os.makedirs(task_dir, exist_ok=True)
    success = False
    try:
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
            if ff_dir:
                ydl_opts["ffmpeg_location"] = ff_dir
            media_type = "audio"
        else:
            # TikTok and other websites
            ydl_opts = {
                "format": "best[ext=mp4]/bestvideo+bestaudio/best",
                "outtmpl": outtmpl,
                "merge_output_format": "mp4",
                "quiet": True,
                "no_warnings": True,
            }
            if ff_dir:
                ydl_opts["ffmpeg_location"] = ff_dir
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

        success = True
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
    finally:
        if not success and task_dir and os.path.exists(task_dir):
            cleanup_task_dir(task_dir)

async def download_generic(url: str, platform: str) -> Dict[str, Any]:
    return await asyncio.to_thread(download_generic_sync, url, platform)
