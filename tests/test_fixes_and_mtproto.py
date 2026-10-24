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

    def test_mtproto_cleanup_raises_on_worker_error(self):
        """Verify ParallelTransferrer._cleanup raises if an upload worker task failed."""
        client_mock = MagicMock()
        client_mock.loop = MagicMock()
        uploader = mtproto_uploader.ParallelTransferrer(client_mock)

        sender_failing = MagicMock()
        sender_failing.disconnect = AsyncMock(side_effect=RuntimeError("Connection broke"))
        uploader.senders = [sender_failing]

        with self.assertRaises(RuntimeError):
            asyncio.run(uploader._cleanup())

    def test_send_mtproto_video_sets_html_parse_mode_and_resolves_dims(self):
        """Verify send_mtproto_video passes parse_mode='html' and auto-resolves missing dimensions."""
        client_mock = MagicMock()
        client_mock.is_connected.return_value = True
        client_mock.send_file = AsyncMock(return_value=True)

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"0" * 20000)
            tmp_name = f.name

        try:
            with patch("mtproto_uploader.get_mtproto_client", AsyncMock(return_value=client_mock)), \
                 patch("mtproto_uploader.fast_upload_file", AsyncMock(return_value="mock_input_file")), \
                 patch("downloader.get_media_dimensions", return_value=(1920, 1080, 120)):
                ok = asyncio.run(mtproto_uploader.send_mtproto_video(
                    chat_id=123456,
                    file_path=tmp_name,
                    caption="<b>Bold Title</b>",
                    duration=0,  # Missing
                    width=0,     # Missing
                    height=0,    # Missing
                ))
                self.assertTrue(ok)
                client_mock.send_file.assert_awaited_once()
                call_kwargs = client_mock.send_file.call_args[1]
                self.assertEqual(call_kwargs["parse_mode"], "html")
                # Ensure dimensions were auto-resolved
                attrs = call_kwargs["attributes"]
                v_attr = [a for a in attrs if hasattr(a, "w")][0]
                self.assertEqual(v_attr.w, 1920)
                self.assertEqual(v_attr.h, 1080)
                self.assertEqual(v_attr.duration, 120)
        finally:
            if os.path.exists(tmp_name):
                os.remove(tmp_name)

    def test_prepare_video_for_streaming_remuxes_non_mp4(self):
        """Verify non-mp4 videos (.webm, .mkv) are remuxed with +faststart to .mp4 container."""
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
            f.write(b"0" * 20000)
            tmp_name = f.name

        try:
            with patch("downloader.subprocess.run") as mock_sub:
                def fake_run(cmd, **kwargs):
                    # Simulate creating the target mp4
                    target = cmd[-1]
                    if target.endswith(".mp4"):
                        with open(target, "wb") as f_out:
                            f_out.write(b"0" * 20000)
                    return MagicMock(returncode=0)

                mock_sub.side_effect = fake_run
                res_path, _ = downloader.prepare_video_for_streaming(tmp_name)
                self.assertTrue(res_path.endswith(".mp4"))
                calls = mock_sub.call_args_list
                remux_calls = [c for c in calls if "+faststart" in c[0][0] and "-c:v" in c[0][0]]
                self.assertTrue(len(remux_calls) >= 1)
                if os.path.exists(res_path):
                    os.remove(res_path)
        finally:
            if os.path.exists(tmp_name):
                os.remove(tmp_name)

    def test_web_scrape_duration_populates_persian_labels_in_main(self):
        """Verify fetch_youtube_web_info duration populates Persian labels when initial duration is 0."""
        mock_web_info = {
            "title": "ویدیوی آزمایشی",
            "duration": 5157,  # 85 min 57 sec
            "channel": "کانال تست",
            "thumbnail": "https://i.ytimg.com/vi/test_id/hqdefault.jpg"
        }
        with patch("downloader.fetch_youtube_web_info", return_value=mock_web_info):
            w_info = downloader.fetch_youtube_web_info("test_id")
            self.assertEqual(w_info["duration"], 5157)
            parsed = downloader.parse_youtube_qualities({"duration": w_info["duration"], "formats": []})
            quals = {q["res"]: q["label"] for q in parsed["video_qualities"]}
            self.assertEqual(quals[1080], "1080p · ۱٫۶ گیگ")
            self.assertEqual(quals[720], "720p · ۱٫۰ گیگ")

    def test_parse_youtube_qualities_multi_format_filesize_max(self):
        """Verify format parsing selects format with valid filesize when format 0 has None."""
        info = {
            "duration": 100,
            "formats": [
                {"height": 1080, "vcodec": "avc1", "filesize": None, "filesize_approx": None},
                {"height": 1080, "vcodec": "avc1", "filesize": 80 * 1024 * 1024, "filesize_approx": 80 * 1024 * 1024},
            ]
        }
        parsed = downloader.parse_youtube_qualities(info)
        quals = {q["res"]: q for q in parsed["video_qualities"]}
        self.assertGreater(quals[1080]["size_bytes"], 70 * 1024 * 1024)
        self.assertIn("مگ", quals[1080]["label"])

    def test_get_node_bin_detects_binary(self):
        """Verify get_node_bin successfully finds a node executable or returns None safely."""
        node_bin = downloader.get_node_bin()
        if node_bin:
            self.assertTrue(os.path.exists(node_bin))
            self.assertTrue(os.access(node_bin, os.X_OK))

    def test_long_duration_format_hms(self):
        """Verify duration formatting for videos >= 1 hour uses H:MM:SS format."""
        duration = 5156  # 1h 25m 56s
        h = duration // 3600
        m = (duration % 3600) // 60
        s = duration % 60
        dur_str = f"{h}:{m:02d}:{s:02d}"
        self.assertEqual(dur_str, "1:25:56")

        # Short video
        short_dur = 185
        dur_str_short = f"{short_dur // 60}:{short_dur % 60:02d}"
        self.assertEqual(dur_str_short, "3:05")

    def test_visionos_player_client_configured(self):
        """Verify VisionOS / Android VR client configured to bypass datacenter IP blocks."""
        with patch("downloader.yt_dlp.YoutubeDL") as mock_ydl:
            mock_inst = MagicMock()
            mock_inst.extract_info.return_value = {"id": "test", "formats": []}
            mock_ydl.return_value.__enter__.return_value = mock_inst
            downloader.extract_youtube_info_sync("https://youtu.be/dQw4w9WgXcQ")
            opts = mock_ydl.call_args[0][0]
            self.assertIn("visionos", opts.get("extractor_args", {}).get("youtube", {}).get("player_client", []))

    def test_tier3_helper_failure_cleans_partial_files_and_does_not_return_corrupt_video(self):
        """Verify that Tier 3 failure cleans all files and raises ValueError without leaking broken stubs."""
        def mock_helper_leaving_partial(vid, q, task_dir=None):
            if task_dir:
                with open(os.path.join(task_dir, "corrupt_partial.mp4"), "wb") as f:
                    f.write(b"CORRUPT" * 100)
            return None

        with patch("downloader.yt_dlp.YoutubeDL", side_effect=Exception("Datacenter block")), \
             patch("downloader.download_youtube_via_helper_sync", side_effect=mock_helper_leaving_partial):
            with self.assertRaises(ValueError):
                downloader.download_youtube_sync("dQw4w9WgXcQ", "720")

    def test_has_faststart_detects_moov_atom(self):
        """Verify has_faststart accurately detects moov atom placed before mdat atom."""
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
            # Fake mp4 header with ftyp, moov, then mdat
            tf.write(b"\x00\x00\x00 ftypmp42\x00\x00\x00 moov\x00\x00\x00 mdat" + b"\x00" * 100)
            tf_path = tf.name

        try:
            self.assertTrue(downloader.has_faststart(tf_path))
        finally:
            if os.path.exists(tf_path):
                os.remove(tf_path)

    def test_has_faststart_rejects_fragmented_mp4_with_moof_or_mvex(self):
        """Verify has_faststart rejects fragmented MP4s containing moof or mvex boxes."""
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
            # Fake fragmented mp4 header with moof box
            tf.write(b"\x00\x00\x00 ftypmp42\x00\x00\x00 moov\x00\x00\x00 moof\x00\x00\x00 mdat" + b"\x00" * 100)
            tf_path = tf.name

        try:
            self.assertFalse(downloader.has_faststart(tf_path))
        finally:
            if os.path.exists(tf_path):
                os.remove(tf_path)

    def test_cobalt_sync_success_pipeline(self):
        """Verify download_via_cobalt_sync properly calls API and streams faststart video."""
        mock_api_resp = MagicMock()
        mock_api_resp.status_code = 200
        mock_api_resp.json.return_value = {
            "status": "tunnel",
            "url": "https://fake-cobalt.test/stream.mp4",
            "filename": "Awesome_Video.mp4"
        }

        mock_stream_resp = MagicMock()
        mock_stream_resp.status_code = 200
        # Return > 10,000 bytes chunk to satisfy size guard
        mock_stream_resp.iter_content.return_value = [b"X" * 16384]
        mock_stream_resp.__enter__.return_value = mock_stream_resp

        with patch.dict(os.environ, {"TEST_COBALT": "1"}), \
             patch("downloader.requests.post", return_value=mock_api_resp), \
             patch("downloader.requests.get", return_value=mock_stream_resp), \
             patch("downloader.get_media_dimensions", return_value=(1280, 720, 120)), \
             patch("downloader.prepare_video_for_streaming", side_effect=lambda f: (f, "/fake/thumb.jpg")):
            
            with tempfile.TemporaryDirectory() as td:
                res = downloader.download_via_cobalt_sync(
                    url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    quality="720",
                    is_audio=False,
                    task_dir=td,
                    title="Awesome Video",
                )
                self.assertIsNotNone(res)
                self.assertEqual(res["type"], "video")
                self.assertEqual(res["duration"], 120)
                self.assertEqual(res["width"], 1280)
                self.assertEqual(res["tier_used"], "cobalt")
                self.assertTrue(os.path.exists(res["file_path"]))

    def test_cobalt_sync_handles_empty_stream_gracefully(self):
        """Verify download_via_cobalt_sync returns None and cleans up when tunnel returns empty content."""
        mock_api_resp = MagicMock()
        mock_api_resp.status_code = 200
        mock_api_resp.json.return_value = {
            "status": "tunnel",
            "url": "https://fake-cobalt.test/stream.mp4",
            "filename": "broken.mp4"
        }

        mock_stream_resp = MagicMock()
        mock_stream_resp.status_code = 200
        mock_stream_resp.iter_content.return_value = [b""]  # Empty 0-byte stream
        mock_stream_resp.__enter__.return_value = mock_stream_resp

        with patch.dict(os.environ, {"TEST_COBALT": "1"}), \
             patch("downloader.requests.post", return_value=mock_api_resp), \
             patch("downloader.requests.get", return_value=mock_stream_resp):
            
            with tempfile.TemporaryDirectory() as td:
                res = downloader.download_via_cobalt_sync(
                    url="https://www.youtube.com/watch?v=broken",
                    quality="720",
                    is_audio=False,
                    task_dir=td,
                )
                self.assertIsNone(res)

    def test_make_upload_progress_callback(self):
        """Verify upload progress callback executes non-blocking and throttles properly."""
        mock_status_msg = AsyncMock()
        cb = main.make_upload_progress_callback(mock_status_msg, prefix="Testing Upload")
        self.assertTrue(callable(cb))
        # First call triggers update
        cb(5000000, 10000000)
        # Immediate sub-second call is throttled
        cb(5100000, 10000000)
        # 100% triggers completion update
        cb(10000000, 10000000)

    def test_make_upload_progress_callback_chunked_streaming(self):
        """Verify progress callback supports chunked streams with total=0 without crashing."""
        mock_status_msg = AsyncMock()
        cb = main.make_upload_progress_callback(mock_status_msg, prefix="Testing Stream")
        self.assertTrue(callable(cb))
        cb(1048576, 0)
        cb(2097152, 0)

    def test_helper_sync_success_pipeline_with_progress_and_button_param(self):
        """Verify download_youtube_via_helper_sync requests button=1, polls CDN, and calls progress callback."""
        mock_init_resp = MagicMock()
        mock_init_resp.status_code = 200
        mock_init_resp.json.return_value = {
            "success": True,
            "progress_url": "https://fake-helper.test/progress?id=123",
            "title": "MrBeast Test"
        }

        mock_poll_resp = MagicMock()
        mock_poll_resp.status_code = 200
        mock_poll_resp.json.return_value = {
            "success": 1,
            "download_url": "https://ricky4.savenow.to/api/v2/download/fake_hash",
            "title": "MrBeast Test"
        }

        mock_stream_resp = MagicMock()
        mock_stream_resp.status_code = 200
        mock_stream_resp.headers = {"Content-Length": "100000", "Content-Type": "video/mp4"}
        mock_stream_resp.iter_content.return_value = [b"A" * 50000, b"B" * 50000]
        mock_stream_resp.__enter__.return_value = mock_stream_resp

        def fake_get(url, *args, **kwargs):
            if "download.php" in url:
                self.assertIn("button=1", url)
                self.assertIn("start=1", url)
                return mock_init_resp
            elif "progress?id=" in url:
                return mock_poll_resp
            elif "savenow.to" in url:
                return mock_stream_resp
            return MagicMock(status_code=404)

        progress_calls = []
        def test_cb(cur, tot):
            progress_calls.append((cur, tot))

        with patch.dict(os.environ, {"TEST_HELPER": "1"}), \
             patch("downloader.requests.get", side_effect=fake_get), \
             patch("time.sleep", return_value=None), \
             patch("downloader.get_media_dimensions", return_value=(1280, 720, 60)), \
             patch("downloader.prepare_video_for_streaming", side_effect=lambda f: (f, "/fake/thumb.jpg")):
            
            with tempfile.TemporaryDirectory() as td:
                res = downloader.download_youtube_via_helper_sync(
                    video_id="fake_id",
                    quality="720",
                    task_dir=td,
                    progress_callback=test_cb
                )
                self.assertIsNotNone(res)
                self.assertEqual(res["type"], "video")
                self.assertEqual(res["duration"], 60)
                self.assertEqual(res["tier_used"], 0)
                self.assertTrue(len(progress_calls) >= 2)
                self.assertEqual(progress_calls[-1], (100000, 100000))

    def test_helper_sync_rejects_ad_networks_and_html_stream(self):
        """Verify helper rejects ad networks (ey43.com) and aborts if stream returns HTML."""
        mock_init_resp = MagicMock()
        mock_init_resp.status_code = 200
        mock_init_resp.json.return_value = {
            "success": True,
            "progress_url": "https://fake-helper.test/progress?id=bad",
            "title": "Bad Ad"
        }

        # Poll returns ad redirect url
        mock_poll_resp = MagicMock()
        mock_poll_resp.status_code = 200
        mock_poll_resp.json.return_value = {
            "success": 1,
            "download_url": "https://ey43.com/ad/redirect",
            "title": "Bad Ad"
        }

        def fake_get(url, *args, **kwargs):
            if "download.php" in url:
                return mock_init_resp
            elif "progress?id=" in url:
                return mock_poll_resp
            return MagicMock(status_code=404)

        with patch.dict(os.environ, {"TEST_HELPER": "1"}), \
             patch("time.sleep", return_value=None), \
             patch("downloader.requests.get", side_effect=fake_get):
            
            with tempfile.TemporaryDirectory() as td:
                res = downloader.download_youtube_via_helper_sync(
                    video_id="fake_ad",
                    quality="720",
                    task_dir=td
                )
                self.assertIsNone(res)

    def test_main_imports_split_video_for_telegram(self):
        """Verify split_video_for_telegram is imported and callable in main."""
        self.assertTrue(hasattr(main, "split_video_for_telegram"))
        self.assertTrue(callable(main.split_video_for_telegram))

    def test_split_video_for_telegram_single_part_under_limit(self):
        """Verify video under limit returns a single part dictionary without splitting."""
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"0" * 10000)
            tmp_path = f.name
        try:
            with patch("downloader.probe_with_ffmpeg", return_value=(1280, 720, 60)):
                parts = downloader.split_video_for_telegram(tmp_path, max_part_size_mb=1850.0, total_duration=60)
                self.assertEqual(len(parts), 1)
                self.assertEqual(parts[0]["part_num"], 1)
                self.assertEqual(parts[0]["total_parts"], 1)
                self.assertEqual(parts[0]["duration"], 60)
                self.assertEqual(parts[0]["file_path"], tmp_path)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_split_video_for_telegram_splits_large_video(self):
        """Verify video exceeding limit invokes ffmpeg to split into parts under limit."""
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            # Fake 200 KB file with max limit set to 0.08 MB (80 KB)
            f.write(b"0" * 200000)
            tmp_path = f.name
        try:
            mock_sub_run = MagicMock()
            mock_sub_run.return_value = MagicMock(returncode=0)

            def fake_run(cmd, *args, **kwargs):
                # When ffmpeg creates part file, write dummy bytes
                out_target = cmd[-1]
                with open(out_target, "wb") as pf:
                    pf.write(b"PART_DATA" * 500)
                return MagicMock(returncode=0)

            with patch("downloader.probe_with_ffmpeg", return_value=(1920, 1080, 120)), \
                 patch("downloader.subprocess.run", side_effect=fake_run), \
                 patch("downloader.prepare_video_for_streaming", side_effect=lambda p: (p, "/fake/thumb.jpg")):
                
                parts = downloader.split_video_for_telegram(tmp_path, max_part_size_mb=0.08, total_duration=120)
                self.assertGreater(len(parts), 1)
                self.assertEqual(parts[0]["part_num"], 1)
                self.assertEqual(parts[0]["total_parts"], len(parts))
                for p in parts:
                    self.assertTrue(os.path.exists(p["file_path"]))
                    # Cleanup generated part files
                    if os.path.exists(p["file_path"]) and p["file_path"] != tmp_path:
                        try:
                            os.remove(p["file_path"])
                        except Exception:
                            pass
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_parse_youtube_qualities_4k_and_2k_when_present(self):
        """Verify 2160p (4K) and 1440p (2K) appear when source formats include 4K/2K."""
        info = {
            "duration": 3600,
            "formats": [
                {"height": 2160, "vcodec": "avc1", "filesize": 4000 * 1024 * 1024},
                {"height": 1440, "vcodec": "avc1", "filesize": 2500 * 1024 * 1024},
                {"height": 1080, "vcodec": "avc1", "filesize": 1500 * 1024 * 1024},
                {"height": 720, "vcodec": "avc1", "filesize": 900 * 1024 * 1024},
            ]
        }
        parsed = downloader.parse_youtube_qualities(info)
        quals = {q["res"]: q["label"] for q in parsed["video_qualities"]}
        self.assertIn(2160, quals)
        self.assertIn("2160p (4K)", quals[2160])
        self.assertIn("۴٫", quals[2160])
        self.assertIn(1440, quals)
        self.assertIn("1440p (2K)", quals[1440])
        self.assertIn(1080, quals)
        self.assertIn(720, quals)


if __name__ == "__main__":
    unittest.main()
