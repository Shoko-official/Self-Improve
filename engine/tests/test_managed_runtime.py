import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from frontier_engine.managed_runtime import verify_bundle


class ManagedRuntimeTests(unittest.TestCase):
    def _write(self, root: Path, content: bytes = b"managed runtime") -> Path:
        executable = root / "bin" / "frontier-engine"
        executable.parent.mkdir()
        executable.write_bytes(content)
        manifest = root / "manifest.json"
        manifest.write_text(json.dumps({"runtime": "frontier-python", "version": "0.1.0", "protocol_version": 1, "platform": "windows", "machine": "amd64", "executable": "bin/frontier-engine", "sha256": hashlib.sha256(content).hexdigest()}), encoding="utf-8")
        return manifest

    def test_bundle_verification_is_exact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self._write(root)
            result = verify_bundle(manifest, root, system="windows", machine="amd64")
            self.assertTrue(result["valid"])

    def test_bundle_rejects_hash_and_platform_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self._write(root)
            manifest_data = json.loads(manifest.read_text())
            manifest_data["sha256"] = "0" * 64
            manifest.write_text(json.dumps(manifest_data), encoding="utf-8")
            self.assertEqual(verify_bundle(manifest, root, system="windows", machine="amd64")["code"], "FR-BUNDLE-HASH-MISMATCH")
            self.assertEqual(verify_bundle(manifest, root, system="linux", machine="amd64")["code"], "FR-BUNDLE-PLATFORM-MISMATCH")

    def test_bundle_rejects_path_escape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self._write(root)
            data = json.loads(manifest.read_text())
            data["executable"] = "../outside"
            manifest.write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(verify_bundle(manifest, root, system="windows", machine="amd64")["code"], "FR-BUNDLE-PATH-ESCAPE")
