import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from frontier_engine.storage import StorageApprovalRequired, StorageProfile, probe_remote_storage


class Handler(BaseHTTPRequestHandler):
    def do_HEAD(self) -> None:
        self.send_response(403); self.end_headers()

    def log_message(self, *_: object) -> None:
        return


class StorageProbeTests(unittest.TestCase):
    def test_probe_requires_approval_and_reports_authentication(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            profile = StorageProfile("s3_compatible", f"http://127.0.0.1:{server.server_port}", "bucket", "project/", "credential")
            with self.assertRaises(StorageApprovalRequired):
                probe_remote_storage(profile, False)
            result = probe_remote_storage(profile, True)
            self.assertEqual((result["state"], result["status"], result["authentication_required"]), ("reachable", 403, True))
        finally:
            server.shutdown(); thread.join(); server.server_close()
