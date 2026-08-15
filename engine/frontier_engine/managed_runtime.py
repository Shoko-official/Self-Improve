"""Verification of packaged managed runtime bundles."""

from __future__ import annotations

import hashlib
import json
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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
