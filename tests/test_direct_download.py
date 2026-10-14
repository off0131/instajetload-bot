import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import unittest
import tempfile
import asyncio
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

import main

class DirectDownloadEndpointTestCase(AioHTTPTestCase):
    async def get_application(self):
        app = web.Application()
        app.router.add_get("/", main.health_check_handler)
        app.router.add_get("/health", main.health_check_handler)
        app.router.add_get("/dl/{token}", main.direct_download_handler)
        return app

    @unittest_run_loop
    async def test_invalid_token_returns_404_html(self):
        resp = await self.client.get("/dl/non-existent-token-12345")
        self.assertEqual(resp.status, 404)
        text = await resp.text()
        self.assertIn("لینک دانلود مستقیم منقضی شده است", text)
        self.assertIn("text/html", resp.headers.get("Content-Type", ""))

    @unittest_run_loop
    async def test_valid_token_streams_file(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
            tf.write(b"SAMPLE_VIDEO_DATA_TEST_12345")
            tf_path = tf.name

        try:
            token = "valid_test_token_abc"
            main.DIRECT_DOWNLOADS[token] = {
                "file_path": tf_path,
                "filename": "Test Video 1080p.mp4",
                "task_dir": None,
                "created_at": 100000.0,
            }

            resp = await self.client.get(f"/dl/{token}")
            self.assertEqual(resp.status, 200)
            self.assertIn("attachment", resp.headers.get("Content-Disposition", ""))
            self.assertIn("video/mp4", resp.headers.get("Content-Type", ""))
            body = await resp.read()
            self.assertEqual(body, b"SAMPLE_VIDEO_DATA_TEST_12345")
        finally:
            if os.path.exists(tf_path):
                os.remove(tf_path)
            main.DIRECT_DOWNLOADS.pop(token, None)

if __name__ == "__main__":
    unittest.main()
