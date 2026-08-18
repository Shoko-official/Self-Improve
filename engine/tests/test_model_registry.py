import tempfile
import json
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from frontier_engine.model_registry import HuggingFaceHub, HuggingFaceHubError, ModelRegistry


class Handler(BaseHTTPRequestHandler):
    large_content = bytes(range(256)) * (5 * 1024 * 1024 // 256)

    def write_throttled(self, content: bytes) -> None:
        try:
            for offset in range(0, len(content), 64 * 1024):
                self.wfile.write(content[offset:offset + 64 * 1024])
                time.sleep(0.001)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            return

    def do_HEAD(self) -> None:
        if self.path in {"/org/model/resolve/main/model.gguf", "/org/model/resolve/main/large.gguf"}:
            content = b"model-bytes" if self.path.endswith("model.gguf") else self.large_content
            self.send_response(200)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("ETag", '"fixture"')
            self.end_headers()
            return
        self.send_response(404); self.end_headers()

    def do_GET(self) -> None:
        if self.path.startswith("/api/models?"):
            body = [{"modelId": "org/model", "sha": "revision", "downloads": 4, "tags": ["gguf"]}]
            self.send_response(200); self.end_headers(); self.wfile.write(json.dumps(body).encode()); return
        if self.path == "/org/model/resolve/main/model.gguf":
            self.send_response(200); self.send_header("Content-Length", "11"); self.end_headers(); self.wfile.write(b"model-bytes"); return
        if self.path == "/org/model/resolve/main/large.gguf":
            range_header = self.headers.get("Range")
            if range_header:
                start_text, end_text = range_header.removeprefix("bytes=").split("-", 1)
                start, end = int(start_text), int(end_text)
                body = self.large_content[start:end + 1]
                self.send_response(206)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Content-Range", f"bytes {start}-{end}/{len(self.large_content)}")
                self.end_headers(); self.write_throttled(body); return
            self.send_response(200); self.send_header("Content-Length", str(len(self.large_content))); self.end_headers(); self.write_throttled(self.large_content); return
        self.send_response(404); self.end_headers()

    def log_message(self, *_: object) -> None: return


class ModelRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.hub = HuggingFaceHub(f"http://127.0.0.1:{self.server.server_port}")

    def tearDown(self) -> None:
        self.server.shutdown(); self.thread.join(); self.server.server_close()

    def test_import_records_hash_without_claiming_runtime_support(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); model = root / "fixture.gguf"; model.write_bytes(b"model")
            registry = ModelRegistry(root / "models.sqlite3")
            self.assertEqual(registry.register(model)["capability_state"], "unvalidated")
            self.assertEqual(registry.list()[0]["format"], "gguf")
            registry.close()

    def test_hub_search_download_hash_and_register_are_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); destination = root / "models" / "model.gguf"
            registry = ModelRegistry(root / "models.sqlite3")
            self.assertEqual(self.hub.search_models("model")[0]["modelId"], "org/model")
            record = registry.download_and_register(self.hub, "org/model", "model.gguf", destination, expected_sha256=__import__("hashlib").sha256(b"model-bytes").hexdigest())
            self.assertEqual(record["model"]["path"], str(destination.resolve()))
            self.assertEqual(record["transfer"]["bytes"], 11)
            registry.close()

    def test_hub_rejects_invalid_paths_and_hash_mismatch_without_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "model.gguf"
            with self.assertRaisesRegex(ValueError, "Invalid Hugging Face"):
                self.hub.download_file("org/model", "../model.gguf", destination)
            with self.assertRaisesRegex(HuggingFaceHubError, "SHA256"):
                self.hub.download_file("org/model", "model.gguf", destination, expected_sha256="0" * 64)
            self.assertFalse(destination.exists())

    def test_hub_cancellation_removes_the_incomplete_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "model.gguf"
            checks = iter((False, True))
            with self.assertRaisesRegex(HuggingFaceHubError, "CANCELLED"):
                self.hub.download_file("org/model", "model.gguf", destination, cancel_requested=lambda: next(checks))
            self.assertFalse(destination.exists())

    def test_hub_plans_and_downloads_large_files_in_parallel(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "large.gguf"
            plan = self.hub.download_plan("org/model", "large.gguf", destination)
            self.assertTrue(plan["accepts_ranges"])
            self.assertEqual(plan["bytes"], len(Handler.large_content))
            self.assertEqual(plan["required_free_bytes"], len(Handler.large_content) * 2)
            self.assertEqual(plan["accelerator"], "parallel-http")
            progress: list[tuple[int, int | None]] = []
            record = self.hub.download_file(
                "org/model",
                "large.gguf",
                destination,
                expected_sha256=__import__("hashlib").sha256(Handler.large_content).hexdigest(),
                progress=lambda received, total: progress.append((received, total)),
            )
            self.assertEqual(record["method"], "parallel-http")
            self.assertGreater(record["segments"], 1)
            self.assertEqual(destination.read_bytes(), Handler.large_content)
            self.assertTrue(progress)

    def test_parallel_download_resumes_retained_segments_after_cancellation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "large.gguf"
            stop = threading.Event()
            def progress(received: int, _total: int | None) -> None:
                if received >= 1024 * 1024:
                    stop.set()
            with self.assertRaisesRegex(HuggingFaceHubError, "CANCELLED"):
                self.hub.download_file("org/model", "large.gguf", destination, cancel_requested=stop.is_set, progress=progress)
            self.assertFalse(destination.exists())
            self.assertTrue(list(destination.parent.glob(".large.gguf.part.*")))
            record = self.hub.download_file("org/model", "large.gguf", destination, workers=4)
            self.assertGreater(record["resumed_bytes"], 0)
            self.assertEqual(destination.read_bytes(), Handler.large_content)
            self.assertFalse(list(destination.parent.glob(".large.gguf.part.*")))
