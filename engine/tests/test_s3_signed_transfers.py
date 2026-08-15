import unittest
from unittest.mock import MagicMock, patch

from frontier_engine.s3_signing import S3Credentials
from frontier_engine.storage import StorageProfile, build_manifest, execute_s3_signed_transfer


class S3SignedTransferTests(unittest.TestCase):
    def test_import_uses_signed_headers_and_returns_verified_content(self) -> None:
        profile = StorageProfile("s3_compatible", "https://storage.example.test", "bucket", "project/", "cloud.primary")
        content = b"remote object"; manifest = build_manifest(profile, "project/result.bin", content, "import")
        response = MagicMock(); response.__enter__.return_value = response; response.read.return_value = content
        with patch("frontier_engine.storage.urllib.request.urlopen", return_value=response) as opened:
            result = execute_s3_signed_transfer(manifest, "us-east-1", S3Credentials("access", "secret"), True)
        request = opened.call_args.args[0]
        self.assertEqual((result["state"], result["content"]), ("succeeded", content))
        self.assertTrue(request.headers["Authorization"].startswith("AWS4-HMAC-SHA256"))
        self.assertNotIn("secret", request.headers["Authorization"])

    def test_export_requires_approval_and_https(self) -> None:
        profile = StorageProfile("s3", "http://storage.example.test", "bucket", "project/", "cloud.primary")
        manifest = build_manifest(profile, "project/result.bin", b"data", "export")
        with self.assertRaisesRegex(PermissionError, "FR-STORAGE-APPROVAL"):
            execute_s3_signed_transfer(manifest, "us-east-1", S3Credentials("access", "secret"), False)
        with self.assertRaisesRegex(ValueError, "FR-S3-TRANSFER-HTTPS"):
            execute_s3_signed_transfer(manifest, "us-east-1", S3Credentials("access", "secret"), True)
