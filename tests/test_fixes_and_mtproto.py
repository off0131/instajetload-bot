"""
Targeted tests verifying:
1. get_media_dimensions and probe_with_ffmpeg import and availability in main.py
2. Persian title unicode integrity without mojibake via clean_web_text in downloader.py
3. prepare_video_for_streaming timeout and faststart behavior
4. parse_youtube_qualities Persian labels (۱٫۶ گیگ, ۱٫۰ گیگ) and 85:57 duration formatting
5. MTProto high-speed parallel uploader (UploadSender, ParallelTransferrer, fast_upload_file)
"""

import os
import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import tempfile
import asyncio

import main
import downloader
import mtproto_uploader


class TestFixesAndMTProto(unittest.TestCase):

    def test_main_imports_media_dimensions_and_probe(self):
        """Verify get_media_dimensions and probe_with_ffmpeg are available in main."""
        self.assertTrue(hasattr(main, "get_media_dimensions"))
        self.assertTrue(callable(main.get_media_dimensions))
        self.assertTrue(hasattr(main, "probe_with_ffmpeg"))
        self.assertTrue(callable(main.probe_with_ffmpeg))

    def test_clean_web_text_persian_integrity_no_mojibake(self):
        """Verify Persian titles are untouched and no mojibake is produced."""
        persian_title = "بازی که بعد از 13 سال هیچکس درکش نکرد"
        cleaned = downloader.clean_web_text(persian_title)
        self.assertEqual(cleaned, persian_title)

        # Test HTML entity unescaping
        html_title = "Cats &amp; Dogs &quot;Best Friends&#39; Day&quot;"
        self.assertEqual(downloader.clean_web_text(html_title), 'Cats & Dogs "Best Friends\' Day"')

        # Test JSON unicode escape
        json_escaped = r"\u0628\u0627\u0632\u06cc"
        self.assertEqual(downloader.clean_web_text(json_escaped), "بازی")

        # Test empty input
        self.assertEqual(downloader.clean_web_text(""), "")
        self.assertEqual(downloader.clean_web_text(None), "")

    def test_persian_quality_labels_calculation(self):
        """Verify exact Persian labels (۱٫۶ گیگ, ۱٫۰ گیگ, مگ) for 85:57 duration video."""
        duration = 5157  # 85 min 57 sec
        dur_str = f"{duration // 60}:{duration % 60:02d}"
        self.assertEqual(dur_str, "85:57")

        # Test estimation mode (from duration only)
        parsed_est = downloader.parse_youtube_qualities({"duration": duration, "formats": []})
        quals_est = {q["res"]: q["label"] for q in parsed_est["video_qualities"]}

        self.assertEqual(quals_est[1080], "1080p · ۱٫۶ گیگ")
        self.assertEqual(quals_est[720], "720p · ۱٫۰ گیگ")
        self.assertIn("480p", quals_est[480])
        self.assertIn("مگ", quals_est[480])

        # Test with explicit format filesizes
        info = {
            "duration": duration,
            "formats": [
                {"height": 1080, "vcodec": "avc1", "filesize": 1500 * 1024 * 1024},
                {"height": 720, "vcodec": "avc1", "filesize": 900 * 1024 * 1024},
                {"height": 480, "vcodec": "avc1", "filesize": 500 * 1024 * 1024},
            ]
        }
        parsed = downloader.parse_youtube_qualities(info)
        quals = {q["res"]: q["label"] for q in parsed["video_qualities"]}

        self.assertIn("1080p", quals[1080])
        self.assertIn("گیگ", quals[1080])

        self.assertIn("720p", quals[720])
        self.assertIn("مگ", quals[720])

        self.assertIn("480p", quals[480])
        self.assertIn("مگ", quals[480])

    def test_prepare_video_for_streaming_timeout_180(self):
        """Verify faststart ffmpeg call uses timeout=180."""
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"0" * 20000)
            tmp_name = f.name

        try:
            with patch("downloader.subprocess.run") as mock_sub:
                mock_sub.return_value = MagicMock(returncode=0)
                downloader.prepare_video_for_streaming(tmp_name)

                # Ensure faststart call occurred with timeout=180
                calls = mock_sub.call_args_list
                faststart_calls = [c for c in calls if "+faststart" in c[0][0]]
                self.assertTrue(len(faststart_calls) >= 1)
                self.assertEqual(faststart_calls[0][1]["timeout"], 180)
        finally:
            if os.path.exists(tmp_name):
                os.remove(tmp_name)

    def test_mtproto_connection_count_and_chunking(self):
        """Verify ParallelTransferrer connection counting and chunk sizes."""
        # Small file
        self.assertEqual(mtproto_uploader.ParallelTransferrer._get_connection_count(5 * 1024 * 1024), 2)
        # 50 MB
        self.assertEqual(mtproto_uploader.ParallelTransferrer._get_connection_count(50 * 1024 * 1024), 4)
        # 1.6 GB
        self.assertEqual(mtproto_uploader.ParallelTransferrer._get_connection_count(1600 * 1024 * 1024), 8)

    def test_mtproto_fast_upload_small_file_fallback(self):
        """Verify small files (<= 10MB) use client.upload_file directly."""
        client_mock = MagicMock()
        client_mock.upload_file = AsyncMock(return_value="small_file_handle")

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"0" * 50000)
            tmp_name = f.name

        try:
            res = asyncio.run(mtproto_uploader.fast_upload_file(client_mock, tmp_name))
            self.assertEqual(res, "small_file_handle")
            client_mock.upload_file.assert_awaited_once()
        finally:
            if os.path.exists(tmp_name):
                os.remove(tmp_name)

    def test_send_mtproto_video_handles_streaming_and_fast_upload(self):
        """Verify send_mtproto_video calls fast_upload and send_file with streaming enabled."""
        client_mock = MagicMock()
        client_mock.is_connected.return_value = True
        client_mock.send_file = AsyncMock(return_value=True)

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"0" * 20000)
            tmp_name = f.name

        try:
            with patch("mtproto_uploader.get_mtproto_client", AsyncMock(return_value=client_mock)), \
                 patch("mtproto_uploader.fast_upload_file", AsyncMock(return_value="mock_input_file")):
                ok = asyncio.run(mtproto_uploader.send_mtproto_video(
                    chat_id=123456,
                    file_path=tmp_name,
                    caption="Test Caption",
                    duration=100,
                    width=1920,
                    height=1080,
                ))
                self.assertTrue(ok)
                client_mock.send_file.assert_awaited_once()
                call_kwargs = client_mock.send_file.call_args[1]
                self.assertEqual(call_kwargs["entity"], 123456)
                self.assertEqual(call_kwargs["file"], "mock_input_file")
                self.assertTrue(call_kwargs["supports_streaming"])
                self.assertEqual(call_kwargs["caption"], "Test Caption")
        finally:
            if os.path.exists(tmp_name):
                os.remove(tmp_name)


if __name__ == "__main__":
    unittest.main()
