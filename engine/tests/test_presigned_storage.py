import hashlib
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from frontier_engine.storage import StorageProfile, build_manifest, execute_presigned_transfer


class Handler(BaseHTTPRequestHandler):
    content = b"remote result"

    def do_GET(self) -> None:
        self.send_response(200); self.end_headers(); self.wfile.write(self.content)

    def do_PUT(self) -> None:
        self.send_response(200); self.end_headers()

    def do_DELETE(self) -> None:
        self.send_response(204); self.end_headers()

    def log_message(self, *_: object) -> None:
        return


class PresignedStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.profile = StorageProfile("s3_compatible", f"http://127.0.0.1:{self.server.server_port}", "bucket", "project/", "credential")
        self.url = f"{self.profile.endpoint}/object?signature=test"

    def tearDown(self) -> None:
        self.server.shutdown(); self.thread.join(); self.server.server_close()

    def test_import_verifies_bytes_from_presigned_url(self) -> None:
        content = Handler.content
        manifest = build_manifest(self.profile, "project/result.bin", content, "import")
        result = execute_presigned_transfer(manifest, self.url, True)
        self.assertEqual((result["state"], result["content"]), ("succeeded", content))

    def test_write_and_delete_require_approval_and_signed_query(self) -> None:
        manifest = build_manifest(self.profile, "project/result.bin", b"new", "export")
        with self.assertRaises(PermissionError):
            execute_presigned_transfer(manifest, self.url, False)
        with self.assertRaisesRegex(ValueError, "FR-STORAGE-PRESIGNED-URL"):
            execute_presigned_transfer(manifest, self.profile.endpoint + "/object", True)
        delete = build_manifest(self.profile, "project/result.bin", b"", "delete")
        self.assertEqual(execute_presigned_transfer(delete, self.url, True)["operation"], "delete")
