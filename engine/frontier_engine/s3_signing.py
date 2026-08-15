"""In-memory AWS SigV4 signing for S3-compatible endpoints."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import parse_qsl, quote, urlparse


@dataclass(frozen=True)
class S3Credentials:
    access_key: str
    secret_key: str
    session_token: str | None = None


@dataclass(frozen=True)
class SignedRequest:
    authorization: str
    headers: dict[str, str]


def _key(secret: bytes, value: str) -> bytes:
    return hmac.new(secret, value.encode(), hashlib.sha256).digest()


def sign_s3_request(method: str, url: str, region: str, credentials: S3Credentials, *, payload: bytes = b"", now: datetime | None = None) -> SignedRequest:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("FR-S3-SIGNING-HTTPS: signed provider requests require HTTPS")
    if not method or not region or not credentials.access_key or not credentials.secret_key:
        raise ValueError("FR-S3-SIGNING-CONFIG: method, region, and credentials are required")
    moment = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    amz_date = moment.strftime("%Y%m%dT%H%M%SZ")
    short_date = moment.strftime("%Y%m%d")
    host = parsed.netloc
    canonical_uri = quote(parsed.path or "/", safe="/-_.~")
    canonical_query = "&".join(f"{quote(key, safe='-_.~')}={quote(value, safe='-_.~')}" for key, value in sorted(parse_qsl(parsed.query, keep_blank_values=True)))
    payload_hash = hashlib.sha256(payload).hexdigest()
    headers = {"host": host, "x-amz-content-sha256": payload_hash, "x-amz-date": amz_date}
    if credentials.session_token:
        headers["x-amz-security-token"] = credentials.session_token
    canonical_headers = "".join(f"{key}:{' '.join(value.strip().split())}\n" for key, value in sorted(headers.items()))
    signed_headers = ";".join(sorted(headers))
    canonical_request = "\n".join((method.upper(), canonical_uri, canonical_query, canonical_headers, signed_headers, payload_hash))
    scope = f"{short_date}/{region}/s3/aws4_request"
    string_to_sign = "AWS4-HMAC-SHA256\n" + amz_date + "\n" + scope + "\n" + hashlib.sha256(canonical_request.encode()).hexdigest()
    signing_key = _key(_key(_key(_key(("AWS4" + credentials.secret_key).encode(), short_date), region), "s3"), "aws4_request")
    signature = hmac.new(signing_key, string_to_sign.encode(), hashlib.sha256).hexdigest()
    authorization = f"AWS4-HMAC-SHA256 Credential={credentials.access_key}/{scope}, SignedHeaders={signed_headers}, Signature={signature}"
    return SignedRequest(authorization, {"Authorization": authorization, "Host": host, "x-amz-content-sha256": payload_hash, "x-amz-date": amz_date, **({"x-amz-security-token": credentials.session_token} if credentials.session_token else {})})
