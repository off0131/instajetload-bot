"""
Shared test fixtures and helpers for instajetload_bot E2E verification suite.
"""

import os
import sys
import tempfile
import shutil
import asyncio
from typing import Dict, Any, List, Optional
from unittest.mock import MagicMock, AsyncMock

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import database
import downloader


class TempDatabaseContext:
    """Creates a temporary isolated SQLite database for testing."""
    def __init__(self):
        self.temp_file = None
        self.orig_db_path = None

    async def __aenter__(self):
        self.temp_file = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        self.temp_file.close()
        self.orig_db_path = database.DB_PATH
        database.DB_PATH = self.temp_file.name
        await database.init_db()
        return self.temp_file.name

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        database.DB_PATH = self.orig_db_path
        if self.temp_file and os.path.exists(self.temp_file.name):
            try:
                os.remove(self.temp_file.name)
            except Exception:
                pass


def make_dummy_media_file(directory: str, filename: str, size_bytes: int = 1024) -> str:
    """Creates a dummy file of exact size in bytes."""
    os.makedirs(directory, exist_ok=True)
    file_path = os.path.join(directory, filename)
    with open(file_path, "wb") as f:
        f.seek(size_bytes - 1)
        f.write(b"\0")
    return file_path


def make_mock_ytdl_info(
    video_id: str = "dQw4w9WgXcQ",
    title: str = "Test Video Title",
    duration: int = 212,
    channel: str = "Test Channel",
    formats: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """Returns sample info dict returned by yt-dlp extract_info."""
    if formats is None:
        formats = [
            {"height": 1080, "vcodec": "avc1"},
            {"height": 720, "vcodec": "avc1"},
            {"height": 480, "vcodec": "avc1"},
            {"height": 360, "vcodec": "avc1"},
            {"height": None, "vcodec": "none", "acodec": "mp4a"},
        ]
    return {
        "id": video_id,
        "title": title,
        "duration": duration,
        "thumbnail": f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg",
        "uploader": channel,
        "channel": channel,
        "formats": formats,
        "description": "Test video description",
    }


def make_mock_spotify_html(
    title: str = "Blinding Lights",
    artist: str = "The Weeknd",
    is_single: bool = True
) -> str:
    """Returns sample Spotify embed / open page HTML with OpenGraph tags."""
    if is_single:
        og_title = f"{title} - Single by {artist}"
    else:
        og_title = f"{title} | Spotify"
    og_desc = f"{artist} · Track · 2020"
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta property="og:title" content="{og_title}">
    <meta property="og:description" content="{og_desc}">
    <meta property="og:type" content="music.song">
</head>
<body>Spotify Mock Page</body>
</html>"""
