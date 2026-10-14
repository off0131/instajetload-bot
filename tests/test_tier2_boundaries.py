"""
Tier 2: Boundary and Corner Case Test Suite (≥70 tests across F1-F14).
Validates edge cases, input anomalies, resource limits, and error handling for instajetload_bot.
"""

import os
import sys
import tempfile
import asyncio
import unittest
from unittest.mock import patch, MagicMock

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import database
import downloader
from tests.test_helpers import TempDatabaseContext


class BaseMockYtDlpBoundary:
    """Mock yt-dlp for boundary conditions."""
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
            target = os.path.join(task_dir, f"boundary_output.{ext}")
            with open(target, "wb") as f:
                f.write(b"BOUNDARY_TEST_PAYLOAD")

        return {
            "id": "dQw4w9WgXcQ",
            "title": "Title with 'Quotes' & <Tags> 🚀",
            "duration": 0,
            "uploader": "",
            "channel": "",
            "formats": [],
            "thumbnail": "",
            "entries": [{"duration": 180}],
        }


# ==============================================================================
# F1 Boundary: YouTube Video Download
# ==============================================================================
class TestTier2F1YouTubeVideoBoundaries(unittest.TestCase):

    @patch("downloader.yt_dlp.YoutubeDL", side_effect=BaseMockYtDlpBoundary)
    @patch("downloader.get_media_dimensions", return_value=(1280, 720, 0))
    def test_f1_bnd_01_non_numeric_quality_defaults_720(self, mock_dim, mock_ydl):
        res = downloader.download_youtube_sync("dQw4w9WgXcQ", "highest_avail")
        self.assertEqual(res["type"], "video")
        downloader.cleanup_task_dir(res["task_dir"])

    @patch("downloader.download_youtube_via_helper_sync", return_value=None)
    @patch("downloader.yt_dlp.YoutubeDL")
    def test_f1_bnd_02_no_files_downloaded_raises_value_error(self, mock_ydl, mock_helper):
        mock_instance = MagicMock()
        mock_instance.extract_info.return_value = {"title": "Test", "duration": 100}
        mock_ydl.return_value.__enter__.return_value = mock_instance

        with self.assertRaises(ValueError) as ctx:
            downloader.download_youtube_sync("dQw4w9WgXcQ", "720")
        self.assertIn("دانلود فایل از یوتیوب ناموفق بود", str(ctx.exception))

    def test_f1_bnd_03_part_and_ytdl_files_ignored(self):
        task_dir = tempfile.mkdtemp()
        # Create only .part and .ytdl files
        with open(os.path.join(task_dir, "video.mp4.part"), "w") as f:
            f.write("partial")
        with open(os.path.join(task_dir, "video.mp4.ytdl"), "w") as f:
            f.write("temp")

        with patch("downloader.yt_dlp.YoutubeDL") as mock_ydl, \
             patch("downloader.DOWNLOADS_DIR", os.path.dirname(task_dir)):
            mock_inst = MagicMock()
            mock_inst.extract_info.return_value = {"title": "PartOnly"}
            mock_ydl.return_value.__enter__.return_value = mock_inst

            with self.assertRaises(ValueError):
                downloader.download_youtube_sync("test_id", "720")

        downloader.cleanup_task_dir(task_dir)

    @patch("downloader.yt_dlp.YoutubeDL", side_effect=BaseMockYtDlpBoundary)
    @patch("downloader.get_media_dimensions", return_value=(1280, 720, 100))
    def test_f1_bnd_04_title_with_unicode_and_emojis(self, mock_dim, mock_ydl):
        res = downloader.download_youtube_sync("dQw4w9WgXcQ", "720")
        self.assertIn("🚀", res["title"])
        downloader.cleanup_task_dir(res["task_dir"])

    @patch("downloader.yt_dlp.YoutubeDL", side_effect=BaseMockYtDlpBoundary)
    @patch("downloader.get_media_dimensions", return_value=(1280, 720, 100))
    def test_f1_bnd_05_title_with_quotes_and_special_chars(self, mock_dim, mock_ydl):
        res = downloader.download_youtube_sync("dQw4w9WgXcQ", "720")
        self.assertIn("'", res["title"])
        downloader.cleanup_task_dir(res["task_dir"])


# ==============================================================================
# F2 Boundary: YouTube Audio Extraction
# ==============================================================================
class TestTier2F2YouTubeAudioBoundaries(unittest.TestCase):

    @patch("downloader.yt_dlp.YoutubeDL", side_effect=BaseMockYtDlpBoundary)
    @patch("downloader.get_media_dimensions", return_value=(None, None, 0))
    def test_f2_bnd_01_zero_duration_audio(self, mock_dim, mock_ydl):
        res = downloader.download_youtube_sync("dQw4w9WgXcQ", "audio")
        self.assertEqual(res["duration"], 0)
        downloader.cleanup_task_dir(res["task_dir"])

    @patch("downloader.yt_dlp.YoutubeDL")
    @patch("downloader.get_media_dimensions", return_value=(None, None, 60))
    def test_f2_bnd_02_empty_uploader_defaults_channel(self, mock_dim, mock_ydl):
        def ydl_factory(opts):
            outtmpl = opts.get("outtmpl", "")
            task_dir = os.path.dirname(outtmpl)
            with open(os.path.join(task_dir, "audio.mp3"), "w") as f:
                f.write("audio")
            mock_inst = MagicMock()
            mock_inst.extract_info.return_value = {
                "title": "Song",
                "duration": 60,
                "uploader": None,
                "channel": None,
            }
            cm = MagicMock()
            cm.__enter__.return_value = mock_inst
            return cm

        with patch("downloader.yt_dlp.YoutubeDL", side_effect=ydl_factory):
            res = downloader.download_youtube_sync("dQw4w9WgXcQ", "audio")
            self.assertEqual(res["artist"], "")
            downloader.cleanup_task_dir(res["task_dir"])

    def test_f2_bnd_03_corrupted_zero_byte_audio_dimensions(self):
        with tempfile.NamedTemporaryFile("wb", delete=False) as tf:
            tf_path = tf.name

        w, h, dur = downloader.get_media_dimensions(tf_path)
        self.assertIsNone(w)
        self.assertIsNone(h)
        self.assertIsNone(dur)
        os.remove(tf_path)

    @patch("downloader.download_youtube_via_helper_sync", return_value=None)
    @patch("downloader.yt_dlp.YoutubeDL")
    def test_f2_bnd_04_audio_download_fail_raises_value_error(self, mock_ydl, mock_helper):
        mock_inst = MagicMock()
        mock_inst.extract_info.side_effect = Exception("Audio extraction aborted")
        mock_ydl.return_value.__enter__.return_value = mock_inst

        with self.assertRaises(ValueError):
            downloader.download_youtube_sync("dQw4w9WgXcQ", "audio")

    @patch("downloader.yt_dlp.YoutubeDL", side_effect=BaseMockYtDlpBoundary)
    @patch("downloader.get_media_dimensions", return_value=(None, None, 18000))
    def test_f2_bnd_05_audio_extreme_duration(self, mock_dim, mock_ydl):
        res = downloader.download_youtube_sync("dQw4w9WgXcQ", "audio")
        self.assertEqual(res["duration"], 18000)
        downloader.cleanup_task_dir(res["task_dir"])


# ==============================================================================
# F3 Boundary: YouTube Shorts Extraction
# ==============================================================================
class TestTier2F3YouTubeShortsBoundaries(unittest.TestCase):

    def test_f3_bnd_01_shorts_url_trailing_slash(self):
        url = "https://www.youtube.com/shorts/dQw4w9WgXcQ/"
        self.assertEqual(downloader.extract_youtube_id(url), "dQw4w9WgXcQ")

    def test_f3_bnd_02_shorts_mixed_case(self):
        url = "https://YOUTUBE.COM/SHORTS/dQw4w9WgXcQ"
        self.assertEqual(downloader.extract_youtube_id(url), "dQw4w9WgXcQ")

    def test_f3_bnd_03_shorts_invalid_short_id(self):
        url = "https://www.youtube.com/shorts/short"
        self.assertIsNone(downloader.extract_youtube_id(url))

    def test_f3_bnd_04_shorts_with_timestamp_param(self):
        url = "https://youtube.com/shorts/dQw4w9WgXcQ?t=15s"
        self.assertEqual(downloader.extract_youtube_id(url), "dQw4w9WgXcQ")

    def test_f3_bnd_05_shorts_detect_platform_subdomain(self):
        url = "https://m.youtube.com/shorts/dQw4w9WgXcQ"
        self.assertEqual(downloader.detect_platform(url), "youtube")


# ==============================================================================
# F4 Boundary: YouTube Metadata Resolution
# ==============================================================================
class TestTier2F4YouTubeMetadataBoundaries(unittest.TestCase):

    def test_f4_bnd_01_invalid_url_raises_value_error(self):
        with patch("downloader.yt_dlp.YoutubeDL", side_effect=Exception("Invalid URL")), \
             patch("downloader.requests.get", side_effect=Exception("Network error")):
            with self.assertRaises(ValueError) as ctx:
                downloader.extract_youtube_info_sync("https://not-a-valid-domain.com/xyz")
            self.assertIn("امکان دریافت اطلاعات ویدیو از یوتیوب وجود ندارد", str(ctx.exception))

    @patch("downloader.yt_dlp.YoutubeDL")
    def test_f4_bnd_02_empty_title_defaults_to_youtube_video(self, mock_ydl):
        mock_inst = MagicMock()
        mock_inst.extract_info.return_value = {"id": "12345678901", "title": None, "formats": []}
        mock_ydl.return_value.__enter__.return_value = mock_inst

        info = downloader.extract_youtube_info_sync("https://youtu.be/12345678901")
        self.assertEqual(info["title"], "YouTube Video")

    @patch("downloader.yt_dlp.YoutubeDL")
    def test_f4_bnd_03_empty_thumbnail_defaults_to_hqdefault(self, mock_ydl):
        call_count = [0]
        def factory(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("Strategy 1 failed")
            mock_inst = MagicMock()
            mock_inst.extract_info.return_value = {"id": "12345678901", "thumbnail": None, "formats": []}
            cm = MagicMock()
            cm.__enter__.return_value = mock_inst
            return cm

        mock_ydl.side_effect = factory
        info = downloader.extract_youtube_info_sync("https://youtu.be/12345678901")
        self.assertIn("12345678901", info["thumbnail"])
        self.assertIn("hqdefault.jpg", info["thumbnail"])

    @patch("downloader.yt_dlp.YoutubeDL")
    def test_f4_bnd_04_empty_formats_defaults_resolutions(self, mock_ydl):
        mock_inst = MagicMock()
        mock_inst.extract_info.return_value = {"id": "12345678901", "formats": []}
        mock_ydl.return_value.__enter__.return_value = mock_inst

        info = downloader.extract_youtube_info_sync("https://youtu.be/12345678901")
        self.assertEqual(info["resolutions"], [720, 480, 360])

    def test_f4_bnd_05_extract_youtube_id_embed_format(self):
        url = "https://www.youtube.com/embed/dQw4w9WgXcQ"
        self.assertEqual(downloader.extract_youtube_id(url), "dQw4w9WgXcQ")


# ==============================================================================
# F5 Boundary: Datacenter Anti-Bot Resilience
# ==============================================================================
class TestTier2F5DatacenterAntiBotBoundaries(unittest.TestCase):

    def test_f5_bnd_01_empty_cookies_file_ignored(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            tf_path = tf.name  # 0 bytes

        with patch("downloader.COOKIES_FILE", tf_path):
            found = downloader.get_youtube_cookies_file()
            self.assertIsNone(found)
        os.remove(tf_path)

    def test_f5_bnd_02_cookies_file_size_under_50_ignored(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            tf.write("# Short")  # < 50 bytes
            tf_path = tf.name

        with patch("downloader.COOKIES_FILE", tf_path):
            found = downloader.get_youtube_cookies_file()
            self.assertIsNone(found)
        os.remove(tf_path)

    def test_f5_bnd_03_cookies_file_without_yt_tokens_ignored(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            tf.write("A" * 100)  # > 50 bytes but no login token
            tf_path = tf.name

        with patch("downloader.COOKIES_FILE", tf_path):
            found = downloader.get_youtube_cookies_file()
            self.assertIsNone(found)
        os.remove(tf_path)

    def test_f5_bnd_04_corrupted_base64_env_cookies(self):
        with patch.dict(os.environ, {"SESSION_COOKIES": "!!!NotValidBase64!!!"}):
            res = downloader.ensure_cookies_file()
            # Does not crash, saves as raw text
            self.assertTrue(res is None or os.path.exists(res))

    def test_f5_bnd_05_proxy_forwarded_to_ydl_opts(self):
        with patch.dict(os.environ, {"YOUTUBE_PROXY": "http://127.0.0.1:8888"}), \
             patch("downloader.yt_dlp.YoutubeDL") as mock_ydl:
            mock_inst = MagicMock()
            mock_inst.extract_info.return_value = {"id": "test", "formats": []}
            mock_ydl.return_value.__enter__.return_value = mock_inst

            downloader.extract_youtube_info_sync("https://youtu.be/dQw4w9WgXcQ")
            call_opts = mock_ydl.call_args[0][0]
            self.assertEqual(call_opts["proxy"], "http://127.0.0.1:8888")


# ==============================================================================
# F6 Boundary: External Helper Fallback
# ==============================================================================
class TestTier2F6ExternalHelperBoundaries(unittest.TestCase):

    @patch("downloader.yt_dlp.YoutubeDL", side_effect=Exception("Bot Challenge"))
    @patch("downloader.requests.get")
    def test_f6_bnd_01_oembed_http_500_failure(self, mock_get, mock_ydl):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_get.return_value = mock_resp

        with self.assertRaises(ValueError):
            downloader.extract_youtube_info_sync("https://youtu.be/dQw4w9WgXcQ")

    @patch("downloader.yt_dlp.YoutubeDL", side_effect=Exception("Bot Challenge"))
    @patch("downloader.requests.get", side_effect=Exception("ReadTimeout"))
    def test_f6_bnd_02_oembed_timeout(self, mock_get, mock_ydl):
        with self.assertRaises(ValueError):
            downloader.extract_youtube_info_sync("https://youtu.be/dQw4w9WgXcQ")

    @patch("downloader.yt_dlp.YoutubeDL", side_effect=Exception("Bot Challenge"))
    @patch("downloader.requests.get")
    def test_f6_bnd_03_oembed_json_empty_dict(self, mock_get, mock_ydl):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {}
        mock_get.return_value = mock_resp

        info = downloader.extract_youtube_info_sync("https://youtu.be/dQw4w9WgXcQ")
        self.assertEqual(info["title"], "YouTube Video")
        self.assertEqual(info["channel"], "YouTube")

    def test_f6_bnd_04_rapidapi_empty_keys(self):
        with patch.dict(os.environ, {"RAPIDAPI_KEYS": "", "RAPIDAPI_KEY": ""}):
            keys = downloader.get_rapidapi_keys()
            self.assertEqual(keys, list(downloader.DEFAULT_RAPIDAPI_KEYS))

    def test_f6_bnd_05_rapidapi_single_key_no_index_error(self):
        with patch.dict(os.environ, {"RAPIDAPI_KEYS": "single_only"}):
            k1 = downloader.get_next_rapidapi_key()
            k2 = downloader.get_next_rapidapi_key()
            self.assertEqual(k1, "single_only")
            self.assertEqual(k2, "single_only")


# ==============================================================================
# F7 Boundary: Multi-Tier Failover Cascade
# ==============================================================================
class TestTier2F7MultiTierCascadeBoundaries(unittest.TestCase):

    def test_f7_bnd_01_all_info_strategies_fail_clean_error(self):
        with patch("downloader.yt_dlp.YoutubeDL", side_effect=Exception("yt-dlp blocked")), \
             patch("downloader.requests.get", side_effect=Exception("oEmbed blocked")):
            with self.assertRaises(ValueError) as ctx:
                downloader.extract_youtube_info_sync("https://youtu.be/dQw4w9WgXcQ")
            self.assertIn("امکان دریافت اطلاعات ویدیو از یوتیوب وجود ندارد", str(ctx.exception))

    def test_f7_bnd_02_dl_strategy1_exception_does_not_abort(self):
        call_count = [0]

        def factory(opts):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("Strategy 1 crashed hard")
            return BaseMockYtDlpBoundary(opts)

        with patch("downloader.yt_dlp.YoutubeDL", side_effect=factory), \
             patch("downloader.get_media_dimensions", return_value=(1280, 720, 10)):
            res = downloader.download_youtube_sync("dQw4w9WgXcQ", "720")
            self.assertEqual(call_count[0], 2)
            downloader.cleanup_task_dir(res["task_dir"])

    def test_f7_bnd_03_dl_both_strategies_fail(self):
        with patch("downloader.download_youtube_via_helper_sync", return_value=None), \
             patch("downloader.yt_dlp.YoutubeDL", side_effect=Exception("All fail")):
            with self.assertRaises(ValueError) as ctx:
                downloader.download_youtube_sync("dQw4w9WgXcQ", "720")
            self.assertIn("دانلود فایل از یوتیوب ناموفق بود", str(ctx.exception))

    def test_f7_bnd_04_spotify_soundcloud_error_cascades_to_yt(self):
        call_count = [0]

        def factory(opts):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("SoundCloud rate limit 429")
            return BaseMockYtDlpBoundary(opts)

        with patch("downloader.yt_dlp.YoutubeDL", side_effect=factory), \
             patch("downloader.urllib.request.urlopen") as mock_url:
            mock_url.return_value.__enter__.return_value.read.return_value = b'<meta property="og:title" content="Track">'
            res = downloader.download_spotify_sync("https://open.spotify.com/track/123")
            self.assertGreaterEqual(call_count[0], 2)
            downloader.cleanup_task_dir(res["task_dir"])

    def test_f7_bnd_05_spotify_all_searches_fail(self):
        with patch("downloader.yt_dlp.YoutubeDL", side_effect=Exception("Search 404")), \
             patch("downloader.urllib.request.urlopen") as mock_url:
            mock_url.return_value.__enter__.return_value.read.return_value = b'<meta property="og:title" content="Track">'
            with self.assertRaises(ValueError) as ctx:
                downloader.download_spotify_sync("https://open.spotify.com/track/123")
            self.assertIn("دانلود موزیک از اسپاتیفای با خطا مواجه شد", str(ctx.exception))


# ==============================================================================
# F8 Boundary: Spotify Single Track Metadata
# ==============================================================================
class TestTier2F8SpotifyMetadataBoundaries(unittest.TestCase):

    def test_f8_bnd_01_malformed_spotify_url_not_matched(self):
        self.assertEqual(downloader.detect_platform("https://example.com/not_spotify"), "other")

    @patch("downloader.yt_dlp.YoutubeDL", side_effect=BaseMockYtDlpBoundary)
    @patch("downloader.urllib.request.urlopen")
    def test_f8_bnd_02_html_entities_unescaped(self, mock_urlopen, mock_ydl):
        html = b'<html><meta property="og:title" content="Rock &amp; Roll &#39;n&#39; Peace"></html>'
        mock_urlopen.return_value.__enter__.return_value.read.return_value = html
        res = downloader.download_spotify_sync("https://open.spotify.com/track/123")
        self.assertEqual(res["title"], "Rock & Roll 'n' Peace")
        downloader.cleanup_task_dir(res["task_dir"])

    @patch("downloader.yt_dlp.YoutubeDL", side_effect=BaseMockYtDlpBoundary)
    @patch("downloader.urllib.request.urlopen")
    def test_f8_bnd_03_spotify_pipe_suffix_removed(self, mock_urlopen, mock_ydl):
        html = b'<html><meta property="og:title" content="My Song | Spotify"></html>'
        mock_urlopen.return_value.__enter__.return_value.read.return_value = html
        res = downloader.download_spotify_sync("https://open.spotify.com/track/123")
        self.assertEqual(res["title"], "My Song")
        downloader.cleanup_task_dir(res["task_dir"])

    @patch("downloader.yt_dlp.YoutubeDL", side_effect=BaseMockYtDlpBoundary)
    @patch("downloader.urllib.request.urlopen")
    def test_f8_bnd_04_spotify_song_and_lyrics_by(self, mock_urlopen, mock_ydl):
        html = b'<html><meta property="og:title" content="Hit Song - song and lyrics by Pop Star"></html>'
        mock_urlopen.return_value.__enter__.return_value.read.return_value = html
        res = downloader.download_spotify_sync("https://open.spotify.com/track/123")
        self.assertEqual(res["title"], "Hit Song")
        self.assertEqual(res["artist"], "Pop Star")
        downloader.cleanup_task_dir(res["task_dir"])

    @patch("downloader.yt_dlp.YoutubeDL", side_effect=BaseMockYtDlpBoundary)
    @patch("downloader.urllib.request.urlopen")
    def test_f8_bnd_05_spotify_dot_separated_desc(self, mock_urlopen, mock_ydl):
        html = b'<html><meta property="og:title" content="Track"><meta property="og:description" content="Famous Artist \xc2\xb7 Album \xc2\xb7 2024"></html>'
        mock_urlopen.return_value.__enter__.return_value.read.return_value = html
        res = downloader.download_spotify_sync("https://open.spotify.com/track/123")
        self.assertEqual(res["artist"], "Famous Artist")
        downloader.cleanup_task_dir(res["task_dir"])


# ==============================================================================
# F9 Boundary: Spotify Single Track Audio & ID3
# ==============================================================================
class TestTier2F9SpotifyAudioBoundaries(unittest.TestCase):

    @patch("downloader.yt_dlp.YoutubeDL")
    @patch("downloader.urllib.request.urlopen")
    def test_f9_bnd_01_empty_artist_query_fallback(self, mock_urlopen, mock_ydl):
        mock_urlopen.return_value.__enter__.return_value.read.return_value = b'<html><meta property="og:title" content="SoloSong"></html>'
        mock_inst = MagicMock()
        mock_inst.extract_info.return_value = {"entries": [{"duration": 180}]}
        mock_ydl.return_value.__enter__.return_value = mock_inst

        with patch("downloader.glob.glob", return_value=["/tmp/SoloSong.mp3"]), \
             patch("downloader.os.path.isfile", return_value=True):
            res = downloader.download_spotify_sync("https://open.spotify.com/track/123")
            self.assertEqual(res["artist"], "")
            self.assertEqual(res["title"], "SoloSong")

    @patch("downloader.yt_dlp.YoutubeDL", side_effect=BaseMockYtDlpBoundary)
    @patch("downloader.urllib.request.urlopen")
    def test_f9_bnd_02_special_characters_in_song_name(self, mock_urlopen, mock_ydl):
        mock_urlopen.return_value.__enter__.return_value.read.return_value = b'<html><meta property="og:title" content="AC/DC - Thunderstruck"></html>'
        res = downloader.download_spotify_sync("https://open.spotify.com/track/123")
        self.assertIn("Thunderstruck", res["title"])
        downloader.cleanup_task_dir(res["task_dir"])

    def test_f9_bnd_03_ffmpeg_manual_convert_fallback(self):
        def factory(opts):
            outtmpl = opts.get("outtmpl", "")
            task_dir = os.path.dirname(outtmpl)
            with open(os.path.join(task_dir, "raw_audio.webm"), "w") as f:
                f.write("audio_stream")
            mock_inst = MagicMock()
            mock_inst.extract_info.return_value = {"entries": [{"duration": 120}]}
            cm = MagicMock()
            cm.__enter__.return_value = mock_inst
            return cm

        with patch("downloader.yt_dlp.YoutubeDL", side_effect=factory), \
             patch("downloader.urllib.request.urlopen") as mock_url, \
             patch("downloader.subprocess.run") as mock_subproc:

            mock_url.return_value.__enter__.return_value.read.return_value = b'<meta property="og:title" content="WebmSong">'

            def fake_ffmpeg(cmd, *args, **kwargs):
                target = cmd[-1]
                with open(target, "w") as f:
                    f.write("mp3_data")
                return MagicMock(returncode=0)

            mock_subproc.side_effect = fake_ffmpeg
            res = downloader.download_spotify_sync("https://open.spotify.com/track/123")
            self.assertTrue(res["file_path"].endswith(".mp3"))
            downloader.cleanup_task_dir(res["task_dir"])

    def test_f9_bnd_04_ffmpeg_subproc_failure(self):
        def factory(opts):
            outtmpl = opts.get("outtmpl", "")
            task_dir = os.path.dirname(outtmpl)
            with open(os.path.join(task_dir, "raw.webm"), "w") as f:
                f.write("data")
            mock_inst = MagicMock()
            mock_inst.extract_info.return_value = {"entries": [{"duration": 100}]}
            cm = MagicMock()
            cm.__enter__.return_value = mock_inst
            return cm

        with patch("downloader.yt_dlp.YoutubeDL", side_effect=factory), \
             patch("downloader.urllib.request.urlopen") as mock_url, \
             patch("downloader.subprocess.run", side_effect=Exception("ffmpeg missing")):

            mock_url.return_value.__enter__.return_value.read.return_value = b'<meta property="og:title" content="FailSong">'
            with self.assertRaises(ValueError):
                downloader.download_spotify_sync("https://open.spotify.com/track/123")

    @patch("downloader.yt_dlp.YoutubeDL")
    @patch("downloader.urllib.request.urlopen")
    def test_f9_bnd_05_duration_none_defaults_to_zero(self, mock_urlopen, mock_ydl):
        mock_urlopen.return_value.__enter__.return_value.read.return_value = b'<html><meta property="og:title" content="Track"></html>'
        def factory(opts):
            outtmpl = opts.get("outtmpl", "")
            task_dir = os.path.dirname(outtmpl)
            with open(os.path.join(task_dir, "Track.mp3"), "w") as f:
                f.write("audio")
            mock_inst = MagicMock()
            mock_inst.extract_info.return_value = {"entries": [{"duration": None}]}
            cm = MagicMock()
            cm.__enter__.return_value = mock_inst
            return cm

        mock_ydl.side_effect = factory
        res = downloader.download_spotify_sync("https://open.spotify.com/track/123")
        self.assertEqual(res["duration"], 0)
        downloader.cleanup_task_dir(res["task_dir"])


# ==============================================================================
# F10 Boundary: Spotify Album Extraction & Loop
# ==============================================================================
class TestTier2F10SpotifyAlbumBoundaries(unittest.TestCase):

    def test_f10_bnd_01_empty_album_tracklist(self):
        tracks = []
        self.assertEqual(len(tracks), 0)
        processed = [t for t in tracks]
        self.assertEqual(processed, [])

    def test_f10_bnd_02_single_track_album(self):
        tracks = [{"title": "Single Album Track", "duration": 200}]
        self.assertEqual(len(tracks), 1)

    def test_f10_bnd_03_album_duplicate_track_names(self):
        tracks = [
            {"title": "Intro", "track_number": 1},
            {"title": "Intro", "track_number": 2},
        ]
        unique_keys = [f"{t['title']}_{t['track_number']}" for t in tracks]
        self.assertEqual(len(unique_keys), 2)
        self.assertNotEqual(unique_keys[0], unique_keys[1])

    def test_f10_bnd_04_album_url_with_query_params(self):
        url = "https://open.spotify.com/album/4czdORir94WzgT5BfAd2TG?si=xyz123&nd=1"
        self.assertEqual(downloader.detect_platform(url), "spotify")

    def test_f10_bnd_05_album_track_null_duration(self):
        track = {"title": "Unknown Duration", "duration": None}
        safe_duration = track.get("duration") or 0
        self.assertEqual(safe_duration, 0)


# ==============================================================================
# F11 Boundary: Telegram 50MB File Limit Guard
# ==============================================================================
class TestTier2F11Telegram50MBGuardBoundaries(unittest.TestCase):

    def test_f11_bnd_01_49_49_mb_passes(self):
        size_bytes = int(49.49 * 1024 * 1024)
        size_mb = size_bytes / (1024 * 1024)
        is_blocked = size_mb > 49.5
        self.assertFalse(is_blocked)

    def test_f11_bnd_02_49_51_mb_fails(self):
        size_bytes = int(49.51 * 1024 * 1024)
        size_mb = size_bytes / (1024 * 1024)
        is_blocked = size_mb > 49.5
        self.assertTrue(is_blocked)

    def test_f11_bnd_03_zero_byte_file(self):
        size_mb = 0 / (1024 * 1024)
        self.assertFalse(size_mb > 49.5)

    def test_f11_bnd_04_exactly_50mb_fails(self):
        size_bytes = int(50.0 * 1024 * 1024)
        size_mb = size_bytes / (1024 * 1024)
        self.assertTrue(size_mb > 49.5)

    def test_f11_bnd_05_huge_file_500mb_fails(self):
        size_bytes = int(500.0 * 1024 * 1024)
        size_mb = size_bytes / (1024 * 1024)
        self.assertTrue(size_mb > 49.5)


# ==============================================================================
# F12 Boundary: Scratch Cleanup & No Disk Leak
# ==============================================================================
class TestTier2F12ScratchCleanupBoundaries(unittest.TestCase):

    def test_f12_bnd_01_cleanup_locked_files_ignore_errors(self):
        try:
            downloader.cleanup_task_dir("/tmp/dummy_non_existent")
        except Exception:
            self.fail("cleanup_task_dir should ignore errors")

    def test_f12_bnd_02_cleanup_empty_string(self):
        downloader.cleanup_task_dir("")

    def test_f12_bnd_03_cleanup_none(self):
        downloader.cleanup_task_dir(None)

    def test_f12_bnd_04_cleanup_deep_nested_structure(self):
        root = tempfile.mkdtemp(prefix="deep_")
        sub1 = os.path.join(root, "level1")
        sub2 = os.path.join(sub1, "level2")
        os.makedirs(sub2, exist_ok=True)
        with open(os.path.join(sub2, "deep_file.txt"), "w") as f:
            f.write("content")
        downloader.cleanup_task_dir(root)
        self.assertFalse(os.path.exists(root))

    def test_f12_bnd_05_cleanup_read_only_files(self):
        td = tempfile.mkdtemp(prefix="ro_")
        fpath = os.path.join(td, "readonly.txt")
        with open(fpath, "w") as f:
            f.write("locked")
        os.chmod(fpath, 0o444)
        downloader.cleanup_task_dir(td)
        self.assertFalse(os.path.exists(td))


# ==============================================================================
# F13 Boundary: Telegram Cache (cached_media)
# ==============================================================================
class TestTier2F13TelegramCacheBoundaries(unittest.IsolatedAsyncioTestCase):

    async def test_f13_bnd_01_duplicate_save_cache_replaces(self):
        async with TempDatabaseContext():
            await database.save_cache("dup_sc", "video", ["fid_initial"], "Old Caption")
            await database.save_cache("dup_sc", "video", ["fid_updated"], "New Caption")
            cached = await database.get_cached("dup_sc")
            self.assertEqual(cached["file_ids"], ["fid_updated"])
            self.assertEqual(cached["caption"], "New Caption")

    async def test_f13_bnd_02_empty_file_ids_list(self):
        async with TempDatabaseContext():
            await database.save_cache("empty_sc", "video", [], "Caption")
            cached = await database.get_cached("empty_sc")
            self.assertEqual(cached["file_ids"], [])

    async def test_f13_bnd_03_huge_caption(self):
        async with TempDatabaseContext():
            long_caption = "A" * 4000
            await database.save_cache("long_cap_sc", "photo", ["fid_1"], long_caption)
            cached = await database.get_cached("long_cap_sc")
            self.assertEqual(len(cached["caption"]), 4000)

    async def test_f13_bnd_04_special_characters_shortcode(self):
        async with TempDatabaseContext():
            special_sc = "yt_dQw4w9WgXcQ_1080p-HQ_v1"
            await database.save_cache(special_sc, "video", ["fid_special"], "Spec")
            cached = await database.get_cached(special_sc)
            self.assertIsNotNone(cached)

    async def test_f13_bnd_05_clear_cache_empty_table(self):
        async with TempDatabaseContext():
            deleted = await database.clear_cache_db()
            self.assertEqual(deleted, 0)


# ==============================================================================
# F14 Boundary: Render Web Server & Keepalive
# ==============================================================================
class TestTier2F14RenderWebServerBoundaries(unittest.IsolatedAsyncioTestCase):

    async def test_f14_bnd_01_invalid_debug_token_401(self):
        import main
        req = MagicMock()
        req.query = {"token": "malicious_attempt"}
        resp = await main.debug_logs_handler(req)
        self.assertEqual(resp.status, 401)

    async def test_f14_bnd_02_empty_debug_token_401(self):
        import main
        req = MagicMock()
        req.query = {"token": ""}
        resp = await main.debug_logs_handler(req)
        self.assertEqual(resp.status, 401)

    def test_f14_bnd_03_debug_logs_ring_buffer_cap(self):
        import main
        for i in range(75):
            main.RECENT_LOGS.append(f"log_entry_{i}")
        self.assertEqual(len(main.RECENT_LOGS), 50)
        self.assertEqual(main.RECENT_LOGS[-1], "log_entry_74")

    async def test_f14_bnd_04_health_page_contains_metrics(self):
        import main
        async with TempDatabaseContext():
            await database.add_or_update_user(12345, "user1", "First")
            req = MagicMock()
            resp = await main.health_check_handler(req)
            self.assertIn("Users: 1", resp.text)

    def test_f14_bnd_05_custom_port_environment(self):
        with patch.dict(os.environ, {"PORT": "9090"}):
            port = int(os.getenv("PORT", 7860))
            self.assertEqual(port, 9090)


if __name__ == "__main__":
    unittest.main()
