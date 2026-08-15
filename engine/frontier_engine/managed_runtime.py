"""Verification of packaged managed runtime bundles."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


@dataclass(frozen=True)
class BundleManifest:
    runtime: str
    version: str
    protocol_version: int
    platform: str
    machine: str
    executable: str
    sha256: str

    @classmethod
    def load(cls, path: Path) -> "BundleManifest":
        try:
            raw: Any = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("FR-BUNDLE-MANIFEST-INVALID") from error
        required = ("runtime", "version", "protocol_version", "platform", "machine", "executable", "sha256")
        if not isinstance(raw, dict) or any(key not in raw for key in required):
            raise ValueError("FR-BUNDLE-MANIFEST-SCHEMA")
        if not isinstance(raw["protocol_version"], int) or raw["protocol_version"] < 1:
            raise ValueError("FR-BUNDLE-MANIFEST-PROTOCOL")
        if not isinstance(raw["sha256"], str) or len(raw["sha256"]) != 64 or any(char not in "0123456789abcdef" for char in raw["sha256"]):
            raise ValueError("FR-BUNDLE-MANIFEST-HASH")
        return cls(*(raw[key] for key in required))


def verify_bundle(manifest_path: Path, bundle_root: Path, *, system: str | None = None, machine: str | None = None) -> dict[str, object]:
    """Verify identity, target platform, containment, and bytes of one bundle."""
    manifest = BundleManifest.load(manifest_path)
    expected_system = system or platform.system().lower()
    expected_machine = machine or platform.machine().lower()
    if manifest.platform.lower() != expected_system or manifest.machine.lower() != expected_machine:
        return {"valid": False, "runtime": manifest.runtime, "version": manifest.version, "code": "FR-BUNDLE-PLATFORM-MISMATCH", "expected": {"platform": expected_system, "machine": expected_machine}, "actual": {"platform": manifest.platform, "machine": manifest.machine}}
    root = bundle_root.resolve()
    executable = (root / manifest.executable).resolve()
    if root not in executable.parents:
        return {"valid": False, "code": "FR-BUNDLE-PATH-ESCAPE"}
    if not executable.is_file():
        return {"valid": False, "code": "FR-BUNDLE-EXECUTABLE-MISSING", "path": str(executable)}
    digest = hashlib.sha256(executable.read_bytes()).hexdigest()
    if digest != manifest.sha256:
        return {"valid": False, "code": "FR-BUNDLE-HASH-MISMATCH", "expected_sha256": manifest.sha256, "actual_sha256": digest}
    return {"valid": True, "runtime": manifest.runtime, "version": manifest.version, "protocol_version": manifest.protocol_version, "path": str(executable), "sha256": digest}


def download_runtime_artifact(url: str, destination: Path, expected_sha256: str, approved: bool, max_bytes: int = 500 * 1024 * 1024, timeout_seconds: float = 120.0) -> dict[str, object]:
    """Download one explicitly approved signed artifact without executing it."""
    parsed = urlparse(url)
    if parsed.scheme != "https" and parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise ValueError("FR-BUNDLE-DOWNLOAD-HTTPS: signed runtime downloads require HTTPS")
    if not parsed.query:
        raise ValueError("FR-BUNDLE-DOWNLOAD-SIGNED: a signed query URL is required")
    if not approved:
        raise PermissionError("FR-BUNDLE-DOWNLOAD-APPROVAL: runtime acquisition requires explicit approval")
    if max_bytes <= 0 or timeout_seconds <= 0:
        raise ValueError("FR-BUNDLE-DOWNLOAD-LIMIT: limits must be positive")
    if len(expected_sha256) != 64 or any(char not in "0123456789abcdef" for char in expected_sha256):
        raise ValueError("FR-BUNDLE-DOWNLOAD-HASH: expected SHA-256 is invalid")
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    total = 0
    digest = hashlib.sha256()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="GET"), timeout=timeout_seconds) as response, temporary.open("wb") as stream:
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError("FR-BUNDLE-DOWNLOAD-TOO-LARGE")
                digest.update(chunk); stream.write(chunk)
        actual = digest.hexdigest()
        if actual != expected_sha256:
            raise ValueError("FR-BUNDLE-DOWNLOAD-HASH-MISMATCH")
        os.replace(temporary, destination)
    except (urllib.error.URLError, TimeoutError) as error:
        raise ValueError(f"FR-BUNDLE-DOWNLOAD-NETWORK:{error}") from error
    finally:
        if temporary.exists(): temporary.unlink()
    return {"state": "downloaded", "path": str(destination), "bytes": total, "sha256": expected_sha256, "executed": False}
