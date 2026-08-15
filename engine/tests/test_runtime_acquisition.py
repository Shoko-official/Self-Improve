import hashlib
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory

from frontier_engine.managed_runtime import download_runtime_artifact


class Handler(BaseHTTPRequestHandler):
    content = b"runtime fixture"

    def do_GET(self) -> None:
        self.send_response(200); self.end_headers(); self.wfile.write(self.content)

    def log_message(self, *_: object) -> None:
        return


class RuntimeAcquisitionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler); self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown(); self.thread.join(); self.server.server_close()

    def test_download_is_approved_atomic_and_non_executing(self) -> None:
        content = Handler.content; digest = hashlib.sha256(content).hexdigest(); url = f"http://127.0.0.1:{self.server.server_port}/runtime?signature=test"
        with TemporaryDirectory() as directory:
            result = download_runtime_artifact(url, Path(directory) / "bin" / "engine", digest, True)
            self.assertEqual((result["state"], result["executed"]), ("downloaded", False))

    def test_download_rejects_missing_approval_and_hash_mismatch(self) -> None:
        url = f"http://127.0.0.1:{self.server.server_port}/runtime?signature=test"
        with TemporaryDirectory() as directory:
            with self.assertRaisesRegex(PermissionError, "FR-BUNDLE-DOWNLOAD-APPROVAL"):
                download_runtime_artifact(url, Path(directory) / "engine", hashlib.sha256(Handler.content).hexdigest(), False)
            with self.assertRaisesRegex(ValueError, "FR-BUNDLE-DOWNLOAD-HASH-MISMATCH"):
                download_runtime_artifact(url, Path(directory) / "engine", "0" * 64, True)
