import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from frontier_engine.image_runtime import ComfyUIAdapter


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/system_stats": body = {"devices": ["cpu"]}
        elif self.path == "/object_info": body = {"KSampler": {}, "SaveImage": {}}
        elif self.path == "/history/job-1": body = {"job-1": {"outputs": {"9": {"images": [{"filename": "result.png", "subfolder": "", "type": "output"}]}}}}
        else: body = {}
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(json.dumps(body).encode())

    def do_POST(self) -> None:
        self.rfile.read(int(self.headers["Content-Length"])); self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b'{"prompt_id":"job-1"}')

    def log_message(self, *_: object) -> None: return


class ComfyUITests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler); self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start(); self.adapter = ComfyUIAdapter(f"http://127.0.0.1:{self.server.server_port}")

    def tearDown(self) -> None:
        self.server.shutdown(); self.thread.join(); self.server.server_close()

    def test_health_submit_and_history_are_real_loopback_contracts(self) -> None:
        self.assertEqual(self.adapter.health()["nodes"], ["KSampler", "SaveImage"])
        with self.assertRaises(PermissionError): self.adapter.submit({"1": {"class_type": "KSampler"}}, approved=False)
        self.assertEqual(self.adapter.submit({"1": {"class_type": "KSampler"}}, approved=True)["prompt_id"], "job-1")
        self.assertEqual(self.adapter.history("job-1")["outputs"][0]["filename"], "result.png")

    def test_rejects_non_loopback_endpoint(self) -> None:
        with self.assertRaisesRegex(ValueError, "LOOPBACK"): ComfyUIAdapter("https://example.com")
