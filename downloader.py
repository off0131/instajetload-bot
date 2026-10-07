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
from typing import Optional, Dict, Any, List
import yt_dlp
from hachoir.parser import createParser
from hachoir.metadata import extractMetadata

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

    # 1. First attempt: yt-dlp
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

def extract_youtube_info_sync(url: str) -> Dict[str, Any]:
    ff_dir = get_ffmpeg_dir()
    ydl_opts: Dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
    }
    if ff_dir:
        ydl_opts["ffmpeg_location"] = ff_dir

    video_id = extract_youtube_id(url)
    clean_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else url

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
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

async def get_youtube_info(url: str) -> Dict[str, Any]:
    return await asyncio.to_thread(extract_youtube_info_sync, url)

def download_youtube_sync(video_id: str, quality: str) -> Dict[str, Any]:
    ff_dir = get_ffmpeg_dir()
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
        if ff_dir:
            ydl_opts["ffmpeg_location"] = ff_dir
        media_type = "audio"
    else:
        q_int = int(quality) if quality.isdigit() else 720
        fmt = (
            f"bestvideo[height<={q_int}]+bestaudio/"
            f"best[height<={q_int}]/best"
        )
        ydl_opts = {
            "format": fmt,
            "outtmpl": outtmpl,
            "merge_output_format": "mp4",
            "postprocessor_args": {"Merger": ["-c:v", "copy", "-c:a", "aac"]},
            "quiet": True,
            "no_warnings": True,
        }
        if ff_dir:
            ydl_opts["ffmpeg_location"] = ff_dir
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
    ff_dir = get_ffmpeg_dir()
    task_id = str(uuid.uuid4())
    task_dir = os.path.join(DOWNLOADS_DIR, task_id)
    os.makedirs(task_dir, exist_ok=True)

    track_title = "Spotify Track"
    artist = ""

    # Follow redirects and scrape metadata
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        )
        with urllib.request.urlopen(req, timeout=12) as r:
            final_url = r.geturl()
            content = r.read().decode("utf-8", errors="ignore")

        import html as py_html
        m_title = re.search(r'<meta property="og:title" content="([^"]+)"', content)
        m_desc = re.search(r'<meta property="og:description" content="([^"]+)"', content)
        if m_title:
            track_title = py_html.unescape(m_title.group(1))
        elif "<title>" in content:
            t_match = re.search(r'<title>(.*?)<\/title>', content)
            if t_match:
                raw_t = py_html.unescape(t_match.group(1)).replace(" | Spotify", "")
                if " - song" in raw_t:
                    track_title = raw_t.split(" - song")[0].strip()

        if m_desc:
            desc_text = py_html.unescape(m_desc.group(1))
            artist = desc_text.split(" · ")[0] if " · " in desc_text else ""
    except Exception as e:
        print(f"Spotify meta fetch note: {e}")

    query = f"{artist} - {track_title} official audio" if artist else f"{track_title} audio"
    outtmpl = os.path.join(task_dir, "%(title)s.%(ext)s")

    ydl_opts: Dict[str, Any] = {
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
    if ff_dir:
        ydl_opts["ffmpeg_location"] = ff_dir

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

def download_twitter_sync(url: str) -> Dict[str, Any]:
    """Downloads Twitter/X media via FxTwitter API, gallery-dl, or yt-dlp."""
    task_id = str(uuid.uuid4())
    task_dir = os.path.join(DOWNLOADS_DIR, task_id)
    os.makedirs(task_dir, exist_ok=True)

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

def download_pinterest_sync(url: str) -> Dict[str, Any]:
    """Downloads Pinterest pin images and videos via gallery-dl or yt-dlp."""
    task_id = str(uuid.uuid4())
    task_dir = os.path.join(DOWNLOADS_DIR, task_id)
    os.makedirs(task_dir, exist_ok=True)

    title = "Pinterest Pin"

    # 1. Tier 1: gallery-dl (handles both images and videos flawlessly)
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
