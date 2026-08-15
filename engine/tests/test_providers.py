import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from frontier_engine.providers import EgressApprovalRequired, NvidiaNimProvider, OpenAICompatibleProvider, ProviderConfig


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps({"data": [{"id": "local-test"}]}).encode())

    def do_POST(self) -> None:
        self.rfile.read(int(self.headers["Content-Length"]))
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        self.wfile.write(b'data: {"choices":[{"delta":{"content":"hello "}}]}\n\n')
        self.wfile.write(b'data: {"choices":[{"delta":{"content":"world"}}]}\n\n')
        self.wfile.write(b"data: [DONE]\n\n")

    def log_message(self, *_: object) -> None:
        return


class ProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown(); self.thread.join(); self.server.server_close()

    def test_health_preview_and_stream_are_real_http_contracts(self) -> None:
        provider = OpenAICompatibleProvider(ProviderConfig("Test endpoint", self.base_url, "secret"))
        self.assertEqual(provider.health()["models"], ["local-test"])
        preview = provider.preview_egress([{"role": "user", "content": "hello"}], [("sample.csv", 12)])
        self.assertEqual((preview.text_bytes, preview.attachment_bytes), (5, 12))
        self.assertEqual("".join(provider.stream_chat("local-test", [{"role": "user", "content": "hello"}], egress_approved=True)), "hello world")

    def test_remote_execution_requires_egress_approval(self) -> None:
        provider = NvidiaNimProvider(self.base_url)
        with self.assertRaises(EgressApprovalRequired):
            list(provider.stream_chat("nim-model", [{"role": "user", "content": "private"}], egress_approved=False))
