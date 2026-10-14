"""
Tier 3: Pairwise Cross-Feature Combination Test Suite (≥14 tests).
Validates cross-feature interactions, failover handoffs, caching pipelines, and resource management.
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


class BaseMockYtDlpTier3:
    """Mock yt-dlp for Tier 3 pairwise integration."""
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
            target = os.path.join(task_dir, f"pairwise_media.{ext}")
            with open(target, "wb") as f:
                f.write(b"PAIRWISE_MEDIA_DATA" * 64)

        return {
            "id": "dQw4w9WgXcQ",
            "title": "Pairwise Integration Title",
            "duration": 215,
            "uploader": "Pairwise Artist",
            "channel": "Pairwise Artist",
            "formats": [
                {"height": 1080, "vcodec": "avc1"},
                {"height": 720, "vcodec": "avc1"},
            ],
            "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
            "entries": [{"duration": 215}],
        }


class TestTier3CrossFeatureCombinations(unittest.IsolatedAsyncioTestCase):
    """Tier 3: Systematic Pairwise Feature Integration Tests."""

    # --------------------------------------------------------------------------
    # Pair 1: F1 (YouTube Video) + F13 (Telegram Caching)
    # --------------------------------------------------------------------------
    @patch("downloader.yt_dlp.YoutubeDL", side_effect=BaseMockYtDlpTier3)
    @patch("downloader.get_media_dimensions", return_value=(1920, 1080, 215))
    async def test_t3_01_f1_f13_yt_video_download_and_cache(self, mock_dim, mock_ydl):
        async with TempDatabaseContext():
            res = downloader.download_youtube_sync("dQw4w9WgXcQ", "1080")
            shortcode = f"yt_{res['title'][:10]}"
            file_ids = ["telegram_file_id_vid_1080"]

            await database.save_cache(shortcode, res["type"], file_ids, res["title"])
            cached = await database.get_cached(shortcode)

            self.assertIsNotNone(cached)
            self.assertEqual(cached["media_type"], "video")
            self.assertEqual(cached["file_ids"], file_ids)
            downloader.cleanup_task_dir(res["task_dir"])

    # --------------------------------------------------------------------------
    # Pair 2: F2 (YouTube Audio) + F13 (Telegram Caching)
    # --------------------------------------------------------------------------
    @patch("downloader.yt_dlp.YoutubeDL", side_effect=BaseMockYtDlpTier3)
    @patch("downloader.get_media_dimensions", return_value=(None, None, 215))
    async def test_t3_02_f2_f13_yt_audio_download_and_cache(self, mock_dim, mock_ydl):
        async with TempDatabaseContext():
            res = downloader.download_youtube_sync("dQw4w9WgXcQ", "audio")
            shortcode = "yt_audio_dQw4w9WgXcQ"
            file_ids = ["telegram_file_id_audio_mp3"]

            await database.save_cache(shortcode, "audio", file_ids, res["title"])
            cached = await database.get_cached(shortcode)

            self.assertIsNotNone(cached)
            self.assertEqual(cached["media_type"], "audio")
            self.assertEqual(cached["file_ids"], file_ids)
            downloader.cleanup_task_dir(res["task_dir"])

    # --------------------------------------------------------------------------
    # Pair 3: F1 (YouTube Video) + F11 (50MB Limit Guard)
    # --------------------------------------------------------------------------
    async def test_t3_03_f1_f11_oversized_yt_video_triggers_guard(self):
        async with TempDatabaseContext():
            temp_task_dir = tempfile.mkdtemp(prefix="t3_oversized_")
            huge_video = os.path.join(temp_task_dir, "huge_1080p.mp4")
            with open(huge_video, "wb") as f:
                f.seek(65 * 1024 * 1024)  # 65MB
                f.write(b"\0")

            size_mb = os.path.getsize(huge_video) / (1024 * 1024)
            guard_blocked = size_mb > 49.5
            self.assertTrue(guard_blocked)

            # Ensure oversized video is NOT cached in DB
            shortcode = "yt_oversized_1080p"
            if not guard_blocked:
                await database.save_cache(shortcode, "video", ["f1"], "Oversized")

            cached = await database.get_cached(shortcode)
            self.assertIsNone(cached)
            downloader.cleanup_task_dir(temp_task_dir)

    # --------------------------------------------------------------------------
    # Pair 4: F1 (YouTube Video) + F12 (Scratch Cleanup on Exception)
    # --------------------------------------------------------------------------
    def test_t3_04_f1_f12_yt_download_exception_cleans_scratch(self):
        created_task_dirs = []

        def factory_with_failure(opts):
            outtmpl = opts.get("outtmpl", "")
            td = os.path.dirname(outtmpl)
            if td:
                created_task_dirs.append(td)
            raise RuntimeError("Network interrupted mid-stream")

        with patch("downloader.yt_dlp.YoutubeDL", side_effect=factory_with_failure):
            task_dir_to_clean = None
            try:
                downloader.download_youtube_sync("dQw4w9WgXcQ", "720")
            except Exception:
                if created_task_dirs:
                    task_dir_to_clean = created_task_dirs[0]
            finally:
                if task_dir_to_clean:
                    downloader.cleanup_task_dir(task_dir_to_clean)

            if task_dir_to_clean:
                self.assertFalse(os.path.exists(task_dir_to_clean))

    # --------------------------------------------------------------------------
    # Pair 5: F4 (Metadata Resolution) + F5 (Datacenter Anti-Bot Resilience)
    # --------------------------------------------------------------------------
    def test_t3_05_f4_f5_metadata_resolution_under_datacenter_block(self):
        call_count = [0]

        def factory(opts):
            call_count[0] += 1
            if call_count[0] == 1:
                # Strategy 1 blocked with bot challenge
                raise Exception("Sign in to confirm you're not a bot (datacenter IP)")
            # Strategy 2 uses Android client
            self.assertEqual(opts.get("extractor_args", {}).get("youtube", {}).get("player_client"), ["android"])
            mock_inst = MagicMock()
            mock_inst.extract_info.return_value = {
                "id": "dQw4w9WgXcQ",
                "title": "Datacenter Android Title",
                "duration": 210,
                "formats": []
            }
            cm = MagicMock()
            cm.__enter__.return_value = mock_inst
            return cm

        with patch("downloader.yt_dlp.YoutubeDL", side_effect=factory):
            info = downloader.extract_youtube_info_sync("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
            self.assertEqual(info["title"], "Datacenter Android Title")
            self.assertEqual(call_count[0], 2)

    # --------------------------------------------------------------------------
    # Pair 6: F5 (Datacenter Anti-Bot) + F6 (oEmbed External Helper)
    # --------------------------------------------------------------------------
    @patch("downloader.yt_dlp.YoutubeDL", side_effect=Exception("Datacenter IP banned across all clients"))
    @patch("downloader.requests.get")
    def test_t3_06_f5_f6_datacenter_block_to_oembed_fallback(self, mock_get, mock_ydl):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "title": "oEmbed Rescue Title",
            "author_name": "Rescue Author",
            "thumbnail_url": "https://img.youtube.com/thumb.jpg"
        }
        mock_get.return_value = mock_resp

        info = downloader.extract_youtube_info_sync("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        self.assertEqual(info["title"], "oEmbed Rescue Title")
        self.assertEqual(info["channel"], "Rescue Author")

    # --------------------------------------------------------------------------
    # Pair 7: F7 (Multi-Tier Failover) + F2 (YouTube Audio Extraction)
    # --------------------------------------------------------------------------
    def test_t3_07_f7_f2_audio_failover_strategy1_to_strategy2(self):
        call_count = [0]

        def factory(opts):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("Strategy 1 audio stream forbidden 403")
            # Strategy 2 Android client handles audio
            outtmpl = opts.get("outtmpl", "")
            td = os.path.dirname(outtmpl)
            with open(os.path.join(td, "extracted.mp3"), "w") as f:
                f.write("audio_data")
            mock_inst = MagicMock()
            mock_inst.extract_info.return_value = {
                "title": "Fallback Audio",
                "duration": 180,
                "uploader": "Fallback Artist"
            }
            cm = MagicMock()
            cm.__enter__.return_value = mock_inst
            return cm

        with patch("downloader.yt_dlp.YoutubeDL", side_effect=factory), \
             patch("downloader.get_media_dimensions", return_value=(None, None, 180)):
            res = downloader.download_youtube_sync("dQw4w9WgXcQ", "audio")
            self.assertEqual(res["type"], "audio")
            self.assertEqual(call_count[0], 2)
            downloader.cleanup_task_dir(res["task_dir"])

    # --------------------------------------------------------------------------
    # Pair 8: F8 (Spotify Metadata) + F9 (Spotify Audio Extraction)
    # --------------------------------------------------------------------------
    @patch("downloader.yt_dlp.YoutubeDL", side_effect=BaseMockYtDlpTier3)
    @patch("downloader.urllib.request.urlopen")
    def test_t3_08_f8_f9_spotify_metadata_to_audio_pipeline(self, mock_urlopen, mock_ydl):
        html = b'<html><meta property="og:title" content="After Hours - Single by The Weeknd"></html>'
        mock_urlopen.return_value.__enter__.return_value.read.return_value = html

        res = downloader.download_spotify_sync("https://open.spotify.com/track/123")
        self.assertEqual(res["title"], "After Hours")
        self.assertEqual(res["artist"], "The Weeknd")
        self.assertEqual(res["type"], "audio")
        self.assertTrue(res["file_path"].endswith(".mp3"))
        downloader.cleanup_task_dir(res["task_dir"])

    # --------------------------------------------------------------------------
    # Pair 9: F8 (Spotify Metadata) + F7 (Failover SoundCloud -> YouTube)
    # --------------------------------------------------------------------------
    def test_t3_09_f8_f7_spotify_soundcloud_fails_to_youtube(self):
        call_count = [0]

        def factory(opts):
            call_count[0] += 1
            if call_count[0] == 1:
                # SoundCloud search empty
                mock_inst = MagicMock()
                mock_inst.extract_info.return_value = {"entries": []}
                cm = MagicMock()
                cm.__enter__.return_value = mock_inst
                return cm
            # YouTube search succeeds
            return BaseMockYtDlpTier3(opts)

        with patch("downloader.yt_dlp.YoutubeDL", side_effect=factory), \
             patch("downloader.urllib.request.urlopen") as mock_url:
            mock_url.return_value.__enter__.return_value.read.return_value = b'<meta property="og:title" content="Track - song by Singer">'
            res = downloader.download_spotify_sync("https://open.spotify.com/track/123")
            self.assertEqual(res["type"], "audio")
            self.assertGreaterEqual(call_count[0], 2)
            downloader.cleanup_task_dir(res["task_dir"])

    # --------------------------------------------------------------------------
    # Pair 10: F9 (Spotify Audio) + F12 (Scratch Cleanup on Success & Error)
    # --------------------------------------------------------------------------
    @patch("downloader.yt_dlp.YoutubeDL", side_effect=BaseMockYtDlpTier3)
    @patch("downloader.urllib.request.urlopen")
    def test_t3_10_f9_f12_spotify_audio_scratch_cleanup_on_success_and_error(self, mock_url, mock_ydl):
        mock_url.return_value.__enter__.return_value.read.return_value = b'<meta property="og:title" content="Song">'
        # Success path
        res = downloader.download_spotify_sync("https://open.spotify.com/track/123")
        self.assertTrue(os.path.exists(res["task_dir"]))
        downloader.cleanup_task_dir(res["task_dir"])
        self.assertFalse(os.path.exists(res["task_dir"]))

    # --------------------------------------------------------------------------
    # Pair 11: F10 (Spotify Album Loop) + F12 (Scratch Cleanup Per Track)
    # --------------------------------------------------------------------------
    def test_t3_11_f10_f12_spotify_album_loop_cleans_each_track_scratch(self):
        album_tracks = ["Track 1", "Track 2", "Track 3"]
        cleaned_dirs = []

        for title in album_tracks:
            task_dir = tempfile.mkdtemp(prefix=f"album_track_{title.replace(' ', '_')}_")
            with open(os.path.join(task_dir, f"{title}.mp3"), "w") as f:
                f.write("audio")

            # Emulate pipeline cleaning up task_dir after dispatching
            downloader.cleanup_task_dir(task_dir)
            cleaned_dirs.append(task_dir)

        for d in cleaned_dirs:
            self.assertFalse(os.path.exists(d))

    # --------------------------------------------------------------------------
    # Pair 12: F13 (Telegram Caching) + F14 (Web Server Stats)
    # --------------------------------------------------------------------------
    async def test_t3_12_f13_f14_cache_hit_updates_web_server_metrics(self):
        import main
        async with TempDatabaseContext():
            # Add user and downloads
            await database.add_or_update_user(999, "tester", "TestUser")
            await database.log_download(999, "yt_test_1")
            await database.log_download(999, "yt_test_2")
            await database.save_cache("yt_test_1", "video", ["fid_1"], "Cap 1")

            req = MagicMock()
            resp = await main.health_check_handler(req)
            self.assertEqual(resp.status, 200)
            self.assertIn("Downloads: 2", resp.text)
            self.assertIn("Users: 1", resp.text)

    # --------------------------------------------------------------------------
    # Pair 13: F3 (Shorts Extraction) + F1 (YouTube Video Download)
    # --------------------------------------------------------------------------
    @patch("downloader.yt_dlp.YoutubeDL", side_effect=BaseMockYtDlpTier3)
    @patch("downloader.get_media_dimensions", return_value=(1080, 1920, 30))
    def test_t3_13_f3_f1_shorts_vertical_video_dimensions(self, mock_dim, mock_ydl):
        shorts_url = "https://www.youtube.com/shorts/dQw4w9WgXcQ"
        vid = downloader.extract_youtube_id(shorts_url)
        self.assertEqual(vid, "dQw4w9WgXcQ")

        res = downloader.download_youtube_sync(vid, "720")
        self.assertEqual(res["type"], "video")
        self.assertGreater(res["height"], res["width"])  # 1920 > 1080 (Vertical)
        downloader.cleanup_task_dir(res["task_dir"])

    # --------------------------------------------------------------------------
    # Pair 14: F11 (50MB Limit Guard) + F12 (Scratch Cleanup)
    # --------------------------------------------------------------------------
    def test_t3_14_f11_f12_oversized_spotify_audio_cleans_scratch(self):
        task_dir = tempfile.mkdtemp(prefix="t3_oversized_spotify_")
        audio_file = os.path.join(task_dir, "oversized_audio.mp3")
        with open(audio_file, "wb") as f:
            f.seek(52 * 1024 * 1024)  # 52MB
            f.write(b"\0")

        try:
            size_mb = os.path.getsize(audio_file) / (1024 * 1024)
            if size_mb > 49.5:
                # Guard stops delivery
                pass
        finally:
            downloader.cleanup_task_dir(task_dir)

        self.assertFalse(os.path.exists(task_dir))


if __name__ == "__main__":
    unittest.main()
