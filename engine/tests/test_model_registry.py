import tempfile
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from frontier_engine.model_registry import HuggingFaceHub, HuggingFaceHubError, ModelRegistry


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path.startswith("/api/models?"):
            body = [{"modelId": "org/model", "sha": "revision", "downloads": 4, "tags": ["gguf"]}]
            self.send_response(200); self.end_headers(); self.wfile.write(json.dumps(body).encode()); return
        if self.path == "/org/model/resolve/main/model.gguf":
            self.send_response(200); self.end_headers(); self.wfile.write(b"model-bytes"); return
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
