import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_managed_engine import target_identity, write_manifest


class ManagedEngineBuildTests(unittest.TestCase):
    def test_target_identity_is_explicit(self) -> None:
        self.assertEqual(target_identity("x86_64-pc-windows-msvc"), ("windows", "x86_64", ".exe"))
        self.assertEqual(target_identity("aarch64-apple-darwin"), ("macos", "aarch64", ""))
        self.assertEqual(target_identity("x86_64-unknown-linux-gnu"), ("linux", "x86_64", ""))
        with self.assertRaisesRegex(ValueError, "FR-BUNDLE-TARGET-UNSUPPORTED"):
            target_identity("wasm32-unknown-unknown")

    def test_manifest_identifies_exact_sidecar_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / "frontier-engine-x86_64-pc-windows-msvc.exe"
            executable.write_bytes(b"managed engine fixture")
            manifest_path = root / "manifest.json"
            result = write_manifest(manifest_path, executable, "x86_64-pc-windows-msvc")
            stored = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(result, stored)
            self.assertEqual(stored["executable"], "frontier-engine.exe")
            self.assertEqual(stored["sha256"], hashlib.sha256(executable.read_bytes()).hexdigest())
