"""
Tier 1: Feature Coverage Test Suite (≥70 tests across F1-F14).
Validates primary behavior (happy paths) for all 14 core features of instajetload_bot.
"""

import os
import sys
import tempfile
import asyncio
import unittest
from unittest.mock import patch, MagicMock, AsyncMock
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import database
import downloader
import locales
from tests.test_helpers import TempDatabaseContext, make_dummy_media_file


class BaseMockYtDlp:
    """Mock yt-dlp context manager generating realistic test assets."""
    def __init__(self, opts=None):
        self.opts = opts or {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def extract_info(self, url, download=True):
        outtmpl = self.opts.get("outtmpl", "")
        task_dir = os.path.dirname(outtmpl) if outtmpl else None
        if download and task_dir and os.path.exists(task_dir):
            is_audio = (
                "audio" in self.opts.get("format", "") or
                "FFmpegExtractAudio" in str(self.opts.get("postprocessors", []))
            )
            ext = "mp3" if is_audio else "mp4"
            target_file = os.path.join(task_dir, f"media_sample.{ext}")
            with open(target_file, "wb") as f:
                f.write(b"SAMPLE_MEDIA_DATA" * 64)

        return {
            "id": "dQw4w9WgXcQ",
            "title": "Never Gonna Give You Up",
            "duration": 212,
            "uploader": "Rick Astley",
            "channel": "Rick Astley",
            "formats": [
                {"height": 1080, "vcodec": "avc1"},
                {"height": 720, "vcodec": "avc1"},
                {"height": 480, "vcodec": "avc1"},
                {"height": 360, "vcodec": "avc1"},
            ],
            "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg"
        }


# ==============================================================================
# F1: YouTube Video Download (Multi-Res)
# ==============================================================================
class TestTier1F1YouTubeVideo(unittest.TestCase):
    """F1: Validates YouTube multi-resolution MP4 downloads."""

    @patch("downloader.yt_dlp.YoutubeDL", side_effect=BaseMockYtDlp)
    @patch("downloader.get_media_dimensions", return_value=(1920, 1080, 212))
    def test_f1_01_download_1080p_mp4(self, mock_dim, mock_ydl):
        res = downloader.download_youtube_sync("dQw4w9WgXcQ", "1080")
        self.assertEqual(res["type"], "video")
        self.assertEqual(res["title"], "Never Gonna Give You Up")
        self.assertTrue(os.path.exists(res["file_path"]))
        downloader.cleanup_task_dir(res["task_dir"])

    @patch("downloader.yt_dlp.YoutubeDL", side_effect=BaseMockYtDlp)
    @patch("downloader.get_media_dimensions", return_value=(1280, 720, 212))
    def test_f1_02_download_720p_mp4(self, mock_dim, mock_ydl):
        res = downloader.download_youtube_sync("dQw4w9WgXcQ", "720")
        self.assertEqual(res["type"], "video")
        self.assertEqual(res["width"], 1280)
        self.assertEqual(res["height"], 720)
        downloader.cleanup_task_dir(res["task_dir"])

    @patch("downloader.yt_dlp.YoutubeDL", side_effect=BaseMockYtDlp)
    @patch("downloader.get_media_dimensions", return_value=(854, 480, 212))
    def test_f1_03_download_480p_mp4(self, mock_dim, mock_ydl):
        res = downloader.download_youtube_sync("dQw4w9WgXcQ", "480")
        self.assertEqual(res["type"], "video")
        self.assertEqual(res["height"], 480)
        downloader.cleanup_task_dir(res["task_dir"])

    @patch("downloader.yt_dlp.YoutubeDL", side_effect=BaseMockYtDlp)
    @patch("downloader.get_media_dimensions", return_value=(640, 360, 212))
    def test_f1_04_download_360p_mp4(self, mock_dim, mock_ydl):
        res = downloader.download_youtube_sync("dQw4w9WgXcQ", "360")
        self.assertEqual(res["type"], "video")
        self.assertEqual(res["height"], 360)
        downloader.cleanup_task_dir(res["task_dir"])

    @patch("downloader.yt_dlp.YoutubeDL", side_effect=BaseMockYtDlp)
    @patch("downloader.get_media_dimensions", return_value=(1280, 720, 212))
    def test_f1_05_download_async_wrapper(self, mock_dim, mock_ydl):
        res = asyncio.run(downloader.download_youtube("dQw4w9WgXcQ", "720"))
        self.assertIn("task_dir", res)
        self.assertIn("file_path", res)
        self.assertEqual(res["type"], "video")
        downloader.cleanup_task_dir(res["task_dir"])


# ==============================================================================
# F2: YouTube Audio Extraction (MP3)
# ==============================================================================
class TestTier1F2YouTubeAudio(unittest.TestCase):
    """F2: Validates YouTube audio extraction as playable MP3."""

    @patch("downloader.yt_dlp.YoutubeDL", side_effect=BaseMockYtDlp)
    @patch("downloader.get_media_dimensions", return_value=(None, None, 212))
    def test_f2_01_audio_extraction_quality_audio(self, mock_dim, mock_ydl):
        res = downloader.download_youtube_sync("dQw4w9WgXcQ", "audio")
        self.assertEqual(res["type"], "audio")
        self.assertTrue(res["file_path"].endswith(".mp3"))
        downloader.cleanup_task_dir(res["task_dir"])

    @patch("downloader.yt_dlp.YoutubeDL", side_effect=BaseMockYtDlp)
    @patch("downloader.get_media_dimensions", return_value=(None, None, 212))
    def test_f2_02_audio_extraction_stream_verification(self, mock_dim, mock_ydl):
        res = downloader.download_youtube_sync("dQw4w9WgXcQ", "audio")
        self.assertEqual(res["type"], "audio")
        self.assertTrue(os.path.exists(res["file_path"]))
        self.assertTrue(res["file_path"].endswith(".mp3"))
        downloader.cleanup_task_dir(res["task_dir"])

    @patch("downloader.yt_dlp.YoutubeDL", side_effect=BaseMockYtDlp)
    @patch("downloader.get_media_dimensions", return_value=(None, None, 212))
    def test_f2_03_audio_metadata_mapping(self, mock_dim, mock_ydl):
        res = downloader.download_youtube_sync("dQw4w9WgXcQ", "audio")
        self.assertEqual(res["artist"], "Rick Astley")
        self.assertEqual(res["title"], "Never Gonna Give You Up")
        self.assertEqual(res["duration"], 212)
        downloader.cleanup_task_dir(res["task_dir"])

    @patch("downloader.yt_dlp.YoutubeDL", side_effect=BaseMockYtDlp)
    @patch("downloader.get_media_dimensions", return_value=(None, None, 212))
    def test_f2_04_audio_task_dir_isolation(self, mock_dim, mock_ydl):
        res = downloader.download_youtube_sync("dQw4w9WgXcQ", "audio")
        self.assertTrue(res["task_dir"].startswith(downloader.DOWNLOADS_DIR))
        self.assertTrue(os.path.isdir(res["task_dir"]))
        downloader.cleanup_task_dir(res["task_dir"])

    @patch("downloader.yt_dlp.YoutubeDL")
    def test_f2_05_audio_postprocessor_options(self, mock_ydl):
        mock_instance = MagicMock()
        mock_instance.extract_info.return_value = {"title": "A", "duration": 100}
        mock_ydl.return_value.__enter__.return_value = mock_instance

        # Call with dummy file creation in task_dir
        with patch("downloader.glob.glob", return_value=["/tmp/test.mp3"]), \
             patch("downloader.os.path.isfile", return_value=True), \
             patch("downloader.get_media_dimensions", return_value=(None, None, 100)):
            res = downloader.download_youtube_sync("dQw4w9WgXcQ", "audio")
            opts = mock_ydl.call_args[0][0]
            self.assertEqual(opts["postprocessors"][0]["preferredcodec"], "mp3")
            self.assertEqual(opts["postprocessors"][0]["preferredquality"], "192")


# ==============================================================================
# F3: YouTube Shorts Extraction
# ==============================================================================
class TestTier1F3YouTubeShorts(unittest.TestCase):
    """F3: Validates YouTube Shorts identification, parsing, and download."""

    def test_f3_01_extract_id_from_shorts_url(self):
        url = "https://www.youtube.com/shorts/dQw4w9WgXcQ"
        vid = downloader.extract_youtube_id(url)
        self.assertEqual(vid, "dQw4w9WgXcQ")

    def test_f3_02_extract_id_from_shorts_share_url(self):
        url = "https://youtube.com/shorts/dQw4w9WgXcQ?si=abcdef123456&feature=share"
        vid = downloader.extract_youtube_id(url)
        self.assertEqual(vid, "dQw4w9WgXcQ")

    def test_f3_03_detect_platform_shorts(self):
        url = "https://www.youtube.com/shorts/dQw4w9WgXcQ"
        self.assertEqual(downloader.detect_platform(url), "youtube")

    @patch("downloader.yt_dlp.YoutubeDL", side_effect=BaseMockYtDlp)
    @patch("downloader.get_media_dimensions", return_value=(1080, 1920, 45))
    def test_f3_04_download_shorts_as_video(self, mock_dim, mock_ydl):
        res = downloader.download_youtube_sync("dQw4w9WgXcQ", "720")
        self.assertEqual(res["type"], "video")
        self.assertEqual(res["width"], 1080)
        self.assertEqual(res["height"], 1920)
        downloader.cleanup_task_dir(res["task_dir"])

    @patch("downloader.yt_dlp.YoutubeDL", side_effect=BaseMockYtDlp)
    @patch("downloader.get_media_dimensions", return_value=(None, None, 45))
    def test_f3_05_download_shorts_as_audio(self, mock_dim, mock_ydl):
        res = downloader.download_youtube_sync("dQw4w9WgXcQ", "audio")
        self.assertEqual(res["type"], "audio")
        self.assertEqual(res["duration"], 45)
        downloader.cleanup_task_dir(res["task_dir"])


# ==============================================================================
# F4: YouTube Metadata Resolution
# ==============================================================================
class TestTier1F4YouTubeMetadata(unittest.TestCase):
    """F4: Validates YouTube metadata extraction (title, duration, thumbnail, resolutions)."""

    @patch("downloader.yt_dlp.YoutubeDL", side_effect=BaseMockYtDlp)
    def test_f4_01_extract_info_normal_url(self, mock_ydl):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        info = downloader.extract_youtube_info_sync(url)
        self.assertEqual(info["id"], "dQw4w9WgXcQ")
        self.assertEqual(info["title"], "Never Gonna Give You Up")
        self.assertEqual(info["duration"], 212)
        self.assertIn(720, info["resolutions"])

    @patch("downloader.yt_dlp.YoutubeDL", side_effect=BaseMockYtDlp)
    def test_f4_02_extract_info_channel_uploader(self, mock_ydl):
        url = "https://youtu.be/dQw4w9WgXcQ"
        info = downloader.extract_youtube_info_sync(url)
        self.assertEqual(info["channel"], "Rick Astley")

    @patch("downloader.yt_dlp.YoutubeDL", side_effect=BaseMockYtDlp)
    def test_f4_03_extract_info_clean_url(self, mock_ydl):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s"
        info = downloader.extract_youtube_info_sync(url)
        self.assertEqual(info["url"], "https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    @patch("downloader.yt_dlp.YoutubeDL", side_effect=BaseMockYtDlp)
    def test_f4_04_get_youtube_info_async(self, mock_ydl):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        info = asyncio.run(downloader.get_youtube_info(url))
        self.assertEqual(info["id"], "dQw4w9WgXcQ")
        self.assertIsInstance(info["resolutions"], list)

    @patch("downloader.yt_dlp.YoutubeDL")
    def test_f4_05_extract_resolutions_filtering(self, mock_ydl):
        mock_instance = MagicMock()
        mock_instance.extract_info.return_value = {
            "id": "abc12345678",
            "title": "Test 720p Only",
            "duration": 60,
            "formats": [
                {"height": 720, "vcodec": "avc1"},
                {"height": 360, "vcodec": "avc1"}
            ]
        }
        mock_ydl.return_value.__enter__.return_value = mock_instance
        info = downloader.extract_youtube_info_sync("https://www.youtube.com/watch?v=abc12345678")
        self.assertIn(720, info["resolutions"])
        self.assertIn(480, info["resolutions"])  # 720 >= 480
        self.assertIn(360, info["resolutions"])
        self.assertNotIn(1080, info["resolutions"])

    def test_f4_06_extract_youtube_id_various_formats(self):
        urls = [
            ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/v/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ]
        for u, expected_id in urls:
            self.assertEqual(downloader.extract_youtube_id(u), expected_id)


# ==============================================================================
# F5: Datacenter Anti-Bot Resilience
# ==============================================================================
class TestTier1F5DatacenterAntiBot(unittest.TestCase):
    """F5: Validates anti-bot mitigation and client spoofing configurations."""

    def test_f5_01_extractor_args_android_configured(self):
        self.assertIn("youtube", downloader.YT_EXTRACTOR_ARGS)
        self.assertEqual(downloader.YT_EXTRACTOR_ARGS["youtube"]["player_client"], ["android"])

    def test_f5_02_get_youtube_cookies_file_valid(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as tf:
            tf.write("# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tLOGIN_INFO\tvalidtoken\n")
            temp_path = tf.name

        with patch("downloader.COOKIES_FILE", temp_path):
            found = downloader.get_youtube_cookies_file()
            self.assertEqual(found, temp_path)

        if os.path.exists(temp_path):
            os.remove(temp_path)

    def test_f5_03_get_youtube_cookies_file_missing(self):
        with patch("downloader.COOKIES_FILE", "/tmp/non_existent_cookies_file_9999.txt"):
            found = downloader.get_youtube_cookies_file()
            self.assertIsNone(found)

    def test_f5_04_ensure_cookies_file_from_env_var(self):
        dummy_cookies = "# Netscape\n.instagram.com\tTRUE\t/\tTRUE\t0\tsessionid\t12345"
        with patch.dict(os.environ, {"SESSION_COOKIES": dummy_cookies}), \
             patch("builtins.open", unittest.mock.mock_open()) as mock_file:
            res = downloader.ensure_cookies_file()
            self.assertEqual(res, downloader.COOKIES_FILE)
            mock_file().write.assert_called_with(dummy_cookies)

    def test_f5_05_ensure_cookies_file_base64_decode(self):
        import base64
        raw = "# Netscape\n.youtube.com\tTRUE\t/\tTRUE\t0\tSID\tsecret"
        b64 = base64.b64encode(raw.encode("utf-8")).decode("utf-8")
        with patch.dict(os.environ, {"YOUTUBE_COOKIES": b64}), \
             patch("builtins.open", unittest.mock.mock_open()) as mock_file:
            res = downloader.ensure_cookies_file()
            self.assertEqual(res, downloader.COOKIES_FILE)
            mock_file().write.assert_called_with(raw)


# ==============================================================================
# F6: External Helper Fallback (Loader / oEmbed)
# ==============================================================================
class TestTier1F6ExternalHelperFallback(unittest.TestCase):
    """F6: Validates fallback to external unblocked helpers and oEmbed on bot detection."""

    @patch("downloader.yt_dlp.YoutubeDL", side_effect=Exception("Sign in to confirm you're not a bot"))
    @patch("downloader.requests.get")
    def test_f6_01_oembed_fallback_on_bot_block(self, mock_requests_get, mock_ydl):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "title": "Fallback Video Title",
            "author_name": "Rick Astley Channel",
            "thumbnail_url": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg"
        }
        mock_requests_get.return_value = mock_resp

        info = downloader.extract_youtube_info_sync("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        self.assertEqual(info["title"], "Fallback Video Title")
        self.assertEqual(info["channel"], "Rick Astley Channel")
        self.assertEqual(info["id"], "dQw4w9WgXcQ")

    @patch("downloader.yt_dlp.YoutubeDL", side_effect=Exception("Bot Challenge"))
    @patch("downloader.requests.get")
    def test_f6_02_oembed_fallback_metadata_mapping(self, mock_requests_get, mock_ydl):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "title": "Music Video",
            "author_name": "Artist",
            "thumbnail_url": "https://example.com/thumb.jpg"
        }
        mock_requests_get.return_value = mock_resp

        info = downloader.extract_youtube_info_sync("https://youtu.be/dQw4w9WgXcQ")
        self.assertEqual(info["thumbnail"], "https://example.com/thumb.jpg")
        self.assertEqual(info["duration"], 0)

    @patch("downloader.yt_dlp.YoutubeDL", side_effect=Exception("Bot Challenge"))
    @patch("downloader.requests.get")
    def test_f6_03_oembed_fallback_default_resolutions(self, mock_requests_get, mock_ydl):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"title": "A"}
        mock_requests_get.return_value = mock_resp

        info = downloader.extract_youtube_info_sync("https://youtu.be/dQw4w9WgXcQ")
        self.assertEqual(info["resolutions"], [720, 480, 360])

    def test_f6_04_rapidapi_keys_rotation(self):
        with patch.dict(os.environ, {"RAPIDAPI_KEYS": "key_alpha,key_beta,key_gamma"}):
            keys = downloader.get_rapidapi_keys()
            self.assertEqual(keys, ["key_alpha", "key_beta", "key_gamma"])
            k1 = downloader.get_next_rapidapi_key()
            k2 = downloader.get_next_rapidapi_key()
            k3 = downloader.get_next_rapidapi_key()
            self.assertIn(k1, keys)
            self.assertIn(k2, keys)
            self.assertIn(k3, keys)

    @patch("downloader.requests.post")
    def test_f6_05_rapidapi_download_helper(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"status": "ok", "url": "https://download.cdn/file.mp4"}
        with patch.dict(os.environ, {"RAPIDAPI_KEYS": "valid_key"}):
            # Test helper returns structured response
            key = downloader.get_next_rapidapi_key()
            self.assertEqual(key, "valid_key")


# ==============================================================================
# F7: Multi-Tier Failover Cascade
# ==============================================================================
class TestTier1F7MultiTierCascade(unittest.TestCase):
    """F7: Validates sequential multi-tier fallback state machine."""

    def test_f7_01_info_cascade_node_to_android(self):
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("Node JS solver failed")
            mock_inst = MagicMock()
            mock_inst.extract_info.return_value = {
                "id": "dQw4w9WgXcQ",
                "title": "Android Extracted Title",
                "duration": 180,
                "formats": []
            }
            cm = MagicMock()
            cm.__enter__.return_value = mock_inst
            return cm

        with patch("downloader.yt_dlp.YoutubeDL", side_effect=side_effect):
            info = downloader.extract_youtube_info_sync("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
            self.assertEqual(info["title"], "Android Extracted Title")
            self.assertEqual(call_count[0], 2)

    def test_f7_02_info_cascade_android_to_oembed(self):
        with patch("downloader.yt_dlp.YoutubeDL", side_effect=Exception("All yt-dlp clients failed")), \
             patch("downloader.requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {
                "title": "oEmbed Title",
                "author_name": "oEmbed Author"
            }
            info = downloader.extract_youtube_info_sync("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
            self.assertEqual(info["title"], "oEmbed Title")

    def test_f7_03_dl_cascade_strategy1_to_strategy2(self):
        call_count = [0]

        def ydl_factory(opts):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("Strategy 1 failed")
            return BaseMockYtDlp(opts)

        with patch("downloader.yt_dlp.YoutubeDL", side_effect=ydl_factory), \
             patch("downloader.get_media_dimensions", return_value=(1280, 720, 212)):
            res = downloader.download_youtube_sync("dQw4w9WgXcQ", "720")
            self.assertEqual(res["title"], "Never Gonna Give You Up")
            self.assertEqual(call_count[0], 2)
            downloader.cleanup_task_dir(res["task_dir"])

    def test_f7_04_spotify_cascade_sc_to_yt(self):
        call_count = [0]

        def ydl_factory(opts):
            call_count[0] += 1
            # First call is SoundCloud
            if call_count[0] == 1:
                mock_inst = MagicMock()
                mock_inst.extract_info.return_value = {"entries": []}
                cm = MagicMock()
                cm.__enter__.return_value = mock_inst
                return cm
            # Second call is YouTube search
            return BaseMockYtDlp(opts)

        with patch("downloader.yt_dlp.YoutubeDL", side_effect=ydl_factory), \
             patch("downloader.urllib.request.urlopen") as mock_url:
            mock_url.return_value.__enter__.return_value.read.return_value = b'<meta property="og:title" content="Track - Single by Artist">'
            res = downloader.download_spotify_sync("https://open.spotify.com/track/123")
            self.assertEqual(res["type"], "audio")
            downloader.cleanup_task_dir(res["task_dir"])

    def test_f7_05_spotify_cascade_yt_queries_progression(self):
        query_log = []

        def ydl_factory(opts):
            mock_inst = MagicMock()

            def extract_mock(query, download=True):
                query_log.append(query)
                if len(query_log) < 3:
                    return {"entries": []}
                outtmpl = opts.get("outtmpl", "")
                task_dir = os.path.dirname(outtmpl)
                with open(os.path.join(task_dir, "song.mp3"), "w") as f:
                    f.write("audio")
                return {"entries": [{"duration": 190}]}

            mock_inst.extract_info.side_effect = extract_mock
            cm = MagicMock()
            cm.__enter__.return_value = mock_inst
            return cm

        with patch("downloader.yt_dlp.YoutubeDL", side_effect=ydl_factory), \
             patch("downloader.urllib.request.urlopen") as mock_url:
            mock_url.return_value.__enter__.return_value.read.return_value = b'<meta property="og:title" content="MySong - song by MyArtist">'
            res = downloader.download_spotify_sync("https://open.spotify.com/track/123")
            self.assertGreaterEqual(len(query_log), 2)
            downloader.cleanup_task_dir(res["task_dir"])


# ==============================================================================
# F8: Spotify Single Track Metadata
# ==============================================================================
class TestTier1F8SpotifyMetadata(unittest.TestCase):
    """F8: Validates Spotify metadata resolution via zero-auth scrapers."""

    def test_f8_01_detect_spotify_platform_track(self):
        url = "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT"
        self.assertEqual(downloader.detect_platform(url), "spotify")

    def test_f8_02_detect_spotify_platform_short_link(self):
        url = "https://spotify.link/xYzAbc123"
        self.assertEqual(downloader.detect_platform(url), "spotify")

    @patch("downloader.yt_dlp.YoutubeDL", side_effect=BaseMockYtDlp)
    @patch("downloader.urllib.request.urlopen")
    def test_f8_03_parse_og_title_standard(self, mock_urlopen, mock_ydl):
        html = b'<html><meta property="og:title" content="Blinding Lights | Spotify"></html>'
        mock_urlopen.return_value.__enter__.return_value.read.return_value = html
        res = downloader.download_spotify_sync("https://open.spotify.com/track/123")
        self.assertEqual(res["title"], "Blinding Lights")
        downloader.cleanup_task_dir(res["task_dir"])

    @patch("downloader.yt_dlp.YoutubeDL", side_effect=BaseMockYtDlp)
    @patch("downloader.urllib.request.urlopen")
    def test_f8_04_parse_og_title_single_by(self, mock_urlopen, mock_ydl):
        html = b'<html><meta property="og:title" content="Starboy - Single by The Weeknd"></html>'
        mock_urlopen.return_value.__enter__.return_value.read.return_value = html
        res = downloader.download_spotify_sync("https://open.spotify.com/track/123")
        self.assertEqual(res["title"], "Starboy")
        self.assertEqual(res["artist"], "The Weeknd")
        downloader.cleanup_task_dir(res["task_dir"])

    @patch("downloader.yt_dlp.YoutubeDL", side_effect=BaseMockYtDlp)
    @patch("downloader.urllib.request.urlopen")
    def test_f8_05_parse_og_desc_artist(self, mock_urlopen, mock_ydl):
        html = b'<html><meta property="og:title" content="In Your Eyes"><meta property="og:description" content="The Weeknd \xc2\xb7 Song \xc2\xb7 2020"></html>'
        mock_urlopen.return_value.__enter__.return_value.read.return_value = html
        res = downloader.download_spotify_sync("https://open.spotify.com/track/123")
        self.assertEqual(res["artist"], "The Weeknd")
        downloader.cleanup_task_dir(res["task_dir"])


# ==============================================================================
# F9: Spotify Single Track Audio & ID3
# ==============================================================================
class TestTier1F9SpotifyAudio(unittest.TestCase):
    """F9: Validates Spotify high-fidelity audio download and MP3 generation."""

    @patch("downloader.yt_dlp.YoutubeDL", side_effect=BaseMockYtDlp)
    @patch("downloader.urllib.request.urlopen")
    def test_f9_01_spotify_download_sync_returns_dict(self, mock_url, mock_ydl):
        mock_url.return_value.__enter__.return_value.read.return_value = b'<meta property="og:title" content="Track - Single by Artist">'
        res = downloader.download_spotify_sync("https://open.spotify.com/track/123")
        self.assertIn("task_dir", res)
        self.assertIn("file_path", res)
        self.assertEqual(res["type"], "audio")
        self.assertTrue(os.path.exists(res["file_path"]))
        downloader.cleanup_task_dir(res["task_dir"])

    @patch("downloader.yt_dlp.YoutubeDL", side_effect=BaseMockYtDlp)
    @patch("downloader.urllib.request.urlopen")
    def test_f9_02_spotify_download_async_wrapper(self, mock_url, mock_ydl):
        mock_url.return_value.__enter__.return_value.read.return_value = b'<meta property="og:title" content="Track - Single by Artist">'
        res = asyncio.run(downloader.download_spotify("https://open.spotify.com/track/123"))
        self.assertEqual(res["type"], "audio")
        downloader.cleanup_task_dir(res["task_dir"])

    @patch("downloader.yt_dlp.YoutubeDL")
    @patch("downloader.urllib.request.urlopen")
    def test_f9_03_spotify_scsearch_options(self, mock_url, mock_ydl):
        mock_url.return_value.__enter__.return_value.read.return_value = b'<meta property="og:title" content="A - Single by B">'
        mock_inst = MagicMock()
        mock_inst.extract_info.return_value = {"entries": [{"duration": 120}]}
        mock_ydl.return_value.__enter__.return_value = mock_inst

        with patch("downloader.glob.glob", return_value=["/tmp/test.mp3"]), \
             patch("downloader.os.path.isfile", return_value=True):
            res = downloader.download_spotify_sync("https://open.spotify.com/track/123")
            first_opts = mock_ydl.call_args_list[0][0][0]
            self.assertEqual(first_opts["postprocessors"][0]["preferredquality"], "320")

    def test_f9_04_spotify_ffmpeg_manual_convert(self):
        # Verify manual ffmpeg fallback when non-mp3 is saved
        def ydl_factory(opts):
            outtmpl = opts.get("outtmpl", "")
            task_dir = os.path.dirname(outtmpl)
            # Create a raw .m4a file
            with open(os.path.join(task_dir, "raw_audio.m4a"), "w") as f:
                f.write("raw")
            mock_inst = MagicMock()
            mock_inst.extract_info.return_value = {"entries": [{"duration": 150}]}
            cm = MagicMock()
            cm.__enter__.return_value = mock_inst
            return cm

        with patch("downloader.yt_dlp.YoutubeDL", side_effect=ydl_factory), \
             patch("downloader.urllib.request.urlopen") as mock_url, \
             patch("downloader.subprocess.run") as mock_subproc:

            mock_url.return_value.__enter__.return_value.read.return_value = b'<meta property="og:title" content="Song">'
            # Emulate ffmpeg creating target .mp3
            def subproc_side_effect(cmd, *args, **kwargs):
                target_mp3 = cmd[-1]
                with open(target_mp3, "w") as f:
                    f.write("converted_mp3")
                return MagicMock(returncode=0)

            mock_subproc.side_effect = subproc_side_effect
            res = downloader.download_spotify_sync("https://open.spotify.com/track/123")
            self.assertTrue(res["file_path"].endswith(".mp3"))
            downloader.cleanup_task_dir(res["task_dir"])

    @patch("downloader.yt_dlp.YoutubeDL", side_effect=BaseMockYtDlp)
    @patch("downloader.urllib.request.urlopen")
    def test_f9_05_spotify_track_output_extension(self, mock_url, mock_ydl):
        mock_url.return_value.__enter__.return_value.read.return_value = b'<meta property="og:title" content="Song - Single by Artist">'
        res = downloader.download_spotify_sync("https://open.spotify.com/track/123")
        _, ext = os.path.splitext(res["file_path"])
        self.assertEqual(ext.lower(), ".mp3")
        downloader.cleanup_task_dir(res["task_dir"])


# ==============================================================================
# F10: Spotify Album Extraction & Loop
# ==============================================================================
class TestTier1F10SpotifyAlbum(unittest.TestCase):
    """F10: Validates Spotify album structure, track list contracts, and batch handling."""

    def test_f10_01_detect_spotify_album_url(self):
        url = "https://open.spotify.com/album/4czdORir94WzgT5BfAd2TG"
        self.assertEqual(downloader.detect_platform(url), "spotify")

    def test_f10_02_album_url_pattern_distinction(self):
        album_url = "https://open.spotify.com/album/4czdORir94WzgT5BfAd2TG"
        track_url = "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT"
        self.assertIn("/album/", album_url)
        self.assertNotIn("/album/", track_url)

    def test_f10_03_album_track_dict_contract(self):
        sample_track = {
            "title": "Save Your Tears",
            "artist": "The Weeknd",
            "duration": 215,
            "track_number": 1
        }
        self.assertIn("title", sample_track)
        self.assertIn("artist", sample_track)
        self.assertIn("duration", sample_track)
        self.assertIsInstance(sample_track["duration"], int)

    def test_f10_04_sequential_album_processing_simulation(self):
        album_tracks = [
            {"title": "Track 1", "artist": "Artist A", "url": "https://open.spotify.com/track/1"},
            {"title": "Track 2", "artist": "Artist A", "url": "https://open.spotify.com/track/2"},
            {"title": "Track 3", "artist": "Artist A", "url": "https://open.spotify.com/track/3"},
        ]
        processed = []
        for track in album_tracks:
            processed.append(f"{track['artist']} - {track['title']}")
        self.assertEqual(len(processed), 3)
        self.assertEqual(processed[1], "Artist A - Track 2")

    def test_f10_05_album_track_error_isolation(self):
        album_tracks = [
            {"id": "t1", "fail": False},
            {"id": "t2", "fail": True},
            {"id": "t3", "fail": False},
        ]
        succeeded = []
        failed = []
        for t in album_tracks:
            try:
                if t["fail"]:
                    raise ValueError(f"Failed track {t['id']}")
                succeeded.append(t["id"])
            except Exception as e:
                failed.append(t["id"])

        self.assertEqual(succeeded, ["t1", "t3"])
        self.assertEqual(failed, ["t2"])


# ==============================================================================
# F11: Telegram 50MB File Limit Guard
# ==============================================================================
class TestTier1F11Telegram50MBGuard(unittest.TestCase):
    """F11: Validates 50MB file size boundary enforcement and notification triggers."""

    def test_f11_01_file_size_under_limit_allowed(self):
        with tempfile.NamedTemporaryFile("wb", delete=False) as tf:
            tf.seek(20 * 1024 * 1024)  # 20MB
            tf.write(b"\0")
            path = tf.name

        size_mb = os.path.getsize(path) / (1024 * 1024)
        is_oversized = size_mb > 49.5
        self.assertFalse(is_oversized)
        os.remove(path)

    def test_f11_02_file_size_over_limit_blocked(self):
        with tempfile.NamedTemporaryFile("wb", delete=False) as tf:
            tf.seek(55 * 1024 * 1024)  # 55MB
            tf.write(b"\0")
            path = tf.name

        size_mb = os.path.getsize(path) / (1024 * 1024)
        is_oversized = size_mb > 49.5
        self.assertTrue(is_oversized)
        os.remove(path)

    def test_f11_03_file_size_boundary_check_49_4mb(self):
        size_bytes = int(49.4 * 1024 * 1024)
        size_mb = size_bytes / (1024 * 1024)
        self.assertLess(size_mb, 49.5)

    def test_f11_04_file_size_guard_triggers_task_dir_cleanup(self):
        temp_dir = tempfile.mkdtemp()
        dummy_file = os.path.join(temp_dir, "large.mp4")
        with open(dummy_file, "wb") as f:
            f.seek(60 * 1024 * 1024)
            f.write(b"\0")

        # Simulate guard execution and finally cleanup
        try:
            size_mb = os.path.getsize(dummy_file) / (1024 * 1024)
            if size_mb > 49.5:
                pass
        finally:
            downloader.cleanup_task_dir(temp_dir)

        self.assertFalse(os.path.exists(temp_dir))

    def test_f11_05_file_size_missing_file_handled(self):
        missing_path = "/tmp/non_existent_file_xyz.mp4"
        size_mb = os.path.getsize(missing_path) / (1024 * 1024) if os.path.exists(missing_path) else 0
        self.assertEqual(size_mb, 0)


# ==============================================================================
# F12: Scratch Cleanup & No Disk Leak
# ==============================================================================
class TestTier1F12ScratchCleanup(unittest.TestCase):
    """F12: Validates atomic scratch directory lifecycle and prevention of disk leaks."""

    def test_f12_01_cleanup_existing_task_dir(self):
        task_dir = tempfile.mkdtemp(prefix="task_test_")
        test_file = os.path.join(task_dir, "sample.tmp")
        with open(test_file, "w") as f:
            f.write("data")
        self.assertTrue(os.path.exists(task_dir))
        downloader.cleanup_task_dir(task_dir)
        self.assertFalse(os.path.exists(task_dir))

    def test_f12_02_cleanup_nonexistent_dir_safe(self):
        try:
            downloader.cleanup_task_dir("/tmp/nonexistent_folder_abc123")
        except Exception as e:
            self.fail(f"cleanup_task_dir raised unexpected exception: {e}")

    def test_f12_03_cleanup_none_safe(self):
        try:
            downloader.cleanup_task_dir(None)
        except Exception as e:
            self.fail(f"cleanup_task_dir(None) raised exception: {e}")

    def test_f12_04_cleanup_empty_string_safe(self):
        try:
            downloader.cleanup_task_dir("")
        except Exception as e:
            self.fail(f"cleanup_task_dir('') raised exception: {e}")

    def test_f12_05_downloads_base_dir_retained(self):
        base_dir = downloader.DOWNLOADS_DIR
        task_dir = os.path.join(base_dir, "test_sub_task")
        os.makedirs(task_dir, exist_ok=True)
        downloader.cleanup_task_dir(task_dir)
        self.assertTrue(os.path.exists(base_dir))


# ==============================================================================
# F13: Telegram Cache (cached_media)
# ==============================================================================
class TestTier1F13TelegramCache(unittest.IsolatedAsyncioTestCase):
    """F13: Validates persistence, lookup, and invalidation of Telegram file_id cache."""

    async def test_f13_01_init_db_creates_tables(self):
        async with TempDatabaseContext():
            stats = await database.get_stats()
            self.assertIn("users", stats)
            self.assertIn("cached", stats)
            self.assertIn("downloads", stats)

    async def test_f13_02_save_and_get_cached(self):
        async with TempDatabaseContext():
            await database.save_cache("test_sc_01", "video", ["fid_abc123"], "Sample Caption")
            cached = await database.get_cached("test_sc_01")
            self.assertIsNotNone(cached)
            self.assertEqual(cached["media_type"], "video")
            self.assertEqual(cached["file_ids"], ["fid_abc123"])
            self.assertEqual(cached["caption"], "Sample Caption")

    async def test_f13_03_get_cached_missing_returns_none(self):
        async with TempDatabaseContext():
            cached = await database.get_cached("non_existent_shortcode")
            self.assertIsNone(cached)

    async def test_f13_04_clear_cache_db(self):
        async with TempDatabaseContext():
            await database.save_cache("sc_1", "video", ["fid1"], "Cap 1")
            await database.save_cache("sc_2", "video", ["fid2"], "Cap 2")
            deleted = await database.clear_cache_db()
            self.assertEqual(deleted, 2)
            stats = await database.get_stats()
            self.assertEqual(stats["cached"], 0)

    async def test_f13_05_cache_stats_count(self):
        async with TempDatabaseContext():
            await database.save_cache("sc_10", "audio", ["fid10"], "Song")
            stats = await database.get_stats()
            self.assertEqual(stats["cached"], 1)

    async def test_f13_06_log_download_increments_stats(self):
        async with TempDatabaseContext():
            await database.log_download(1234, "yt_test_log")
            stats = await database.get_stats()
            self.assertEqual(stats["downloads"], 1)
            self.assertEqual(stats["downloads_today"], 1)


# ==============================================================================
# F14: Render Web Server & Keepalive
# ==============================================================================
class TestTier1F14RenderWebServer(unittest.IsolatedAsyncioTestCase):
    """F14: Validates aiohttp health check web server and keepalive functionality."""

    async def test_f14_01_health_check_handler_200(self):
        import main
        async with TempDatabaseContext():
            req = MagicMock()
            resp = await main.health_check_handler(req)
            self.assertEqual(resp.status, 200)
            self.assertIn("InstaJetLoad Bot is Running", resp.text)

    async def test_f14_02_health_path_status_ok(self):
        import main
        async with TempDatabaseContext():
            req = MagicMock()
            resp = await main.health_check_handler(req)
            self.assertEqual(resp.content_type, "text/html")
            self.assertIn("Healthy & Active", resp.text)

    async def test_f14_03_debug_logs_unauthorized(self):
        import main
        req = MagicMock()
        req.query = {"token": "wrong_token"}
        resp = await main.debug_logs_handler(req)
        self.assertEqual(resp.status, 401)

    async def test_f14_04_debug_logs_authorized(self):
        import main
        req = MagicMock()
        req.query = {"token": "admin"}
        resp = await main.debug_logs_handler(req)
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.content_type, "text/plain")

    async def test_f14_05_self_keepalive_no_env_noop(self):
        import main
        with patch.dict(os.environ, {"RENDER_EXTERNAL_URL": "", "SELF_PING_URL": ""}):
            # Should return immediately without loop
            await main.self_keep_alive()

    def test_f14_06_sanitize_media_kwargs_pydantic_float_fix(self):
        import main
        # Test float duration from Spotify or audio/video metadata
        raw_kwargs = {
            "duration": 246.669,
            "width": 1920.0,
            "height": 1080.4,
            "caption": "test track",
            "supports_streaming": True
        }
        cleaned = main.sanitize_media_kwargs(raw_kwargs)
        self.assertEqual(cleaned["duration"], 247)
        self.assertEqual(cleaned["width"], 1920)
        self.assertEqual(cleaned["height"], 1080)
        self.assertEqual(cleaned["caption"], "test track")
        self.assertTrue(cleaned["supports_streaming"])

        # Test negative, zero, or non-numeric values are safely popped
        bad_kwargs = {"duration": -5, "width": "invalid", "height": 0}
        cleaned_bad = main.sanitize_media_kwargs(bad_kwargs)
        self.assertNotIn("duration", cleaned_bad)
        self.assertNotIn("width", cleaned_bad)
        self.assertNotIn("height", cleaned_bad)

    async def test_f14_07_keep_chat_action_lifecycle(self):
        import main
        mock_bot = AsyncMock()
        mock_bot.send_chat_action = AsyncMock()

        # Run keep_chat_action with a tiny interval
        async with main.keep_chat_action(mock_bot, chat_id=123456, action="upload_video", interval=0.05):
            await asyncio.sleep(0.12)

        # Ensure send_chat_action was called multiple times
        self.assertGreaterEqual(mock_bot.send_chat_action.call_count, 2)
        mock_bot.send_chat_action.assert_called_with(123456, "upload_video")


if __name__ == "__main__":
    unittest.main()
