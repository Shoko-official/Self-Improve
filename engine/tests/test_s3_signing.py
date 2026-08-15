import unittest
from datetime import datetime, timezone

from frontier_engine.s3_signing import S3Credentials, sign_s3_request


class S3SigningTests(unittest.TestCase):
    def test_signature_is_deterministic_and_contains_no_secret(self) -> None:
        credentials = S3Credentials("AKIAEXAMPLE", "secret-key", "session-token")
        result = sign_s3_request("GET", "https://storage.example.test/bucket/object?x=1", "us-east-1", credentials, now=datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc))
        self.assertIn("Credential=AKIAEXAMPLE/20240102/us-east-1/s3/aws4_request", result.authorization)
        self.assertNotIn("secret-key", result.authorization)
        self.assertEqual(result.headers["x-amz-date"], "20240102T030405Z")
        self.assertEqual(result, sign_s3_request("GET", "https://storage.example.test/bucket/object?x=1", "us-east-1", credentials, now=datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc)))

    def test_signing_rejects_non_https(self) -> None:
        with self.assertRaisesRegex(ValueError, "FR-S3-SIGNING-HTTPS"):
            sign_s3_request("GET", "http://storage.example.test/object", "us-east-1", S3Credentials("a", "b"))
