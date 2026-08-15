import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from frontier_engine.storage import StorageProfile, StorageApprovalRequired, list_presigned_objects


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps({"Contents": [{"Key": "project/a.csv", "Size": 4, "ETag": "etag"}, {"Key": "other/hidden", "Size": 9}]}).encode())

    def log_message(self, *_: object) -> None:
        return


class PresignedListingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler); self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.profile = StorageProfile("s3_compatible", f"http://127.0.0.1:{self.server.server_port}", "bucket", "project/", "credential")

    def tearDown(self) -> None:
        self.server.shutdown(); self.thread.join(); self.server.server_close()

    def test_listing_is_approved_bounded_and_prefix_scoped(self) -> None:
        url=f"{self.profile.endpoint}/list?signature=test"
        with self.assertRaises(StorageApprovalRequired): list_presigned_objects(self.profile, url, False)
        result=list_presigned_objects(self.profile, url, True)
        self.assertEqual((result["count"], result["objects"][0]["key"]), (1, "project/a.csv"))
