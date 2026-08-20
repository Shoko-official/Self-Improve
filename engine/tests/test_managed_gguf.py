import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from frontier_engine.managed_gguf import _runtime_command, _server_command, install_managed_gguf, probe_managed_gguf


class ManagedGgufTests(unittest.TestCase):
    def test_pinned_runtime_install_verifies_and_extracts_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "fixture.zip"
            with zipfile.ZipFile(fixture, "w") as archive:
                archive.writestr("runtime/llama-cli.exe", b"fixture")
                archive.writestr("runtime/llama-cli", b"fixture")
            digest = hashlib.sha256(fixture.read_bytes()).hexdigest()

            def copy_fixture(_url: str, destination: Path, expected_bytes: int) -> None:
                self.assertEqual(expected_bytes, fixture.stat().st_size)
                destination.write_bytes(fixture.read_bytes())

            with patch("frontier_engine.managed_gguf._platform_key", return_value="fixture"), patch.dict("frontier_engine.managed_gguf.ASSETS", {"fixture": ("fixture.zip", digest, fixture.stat().st_size)}), patch("frontier_engine.managed_gguf._download", side_effect=copy_fixture), patch("frontier_engine.managed_gguf._probe_executable", return_value=(True, None, 0)):
                installed = install_managed_gguf(root)
                reused = install_managed_gguf(root)
            self.assertTrue(installed["available"])
            self.assertTrue(installed["installed"])
            self.assertTrue(reused["reused"])
            self.assertTrue(Path(str(probe_managed_gguf(root)["path"])).is_file())
            self.assertTrue((root / "runtimes" / "shoko-gguf" / "b10517" / "shoko-runtime-receipt.json").is_file())

    def test_missing_runtime_is_reported_without_lm_studio_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = probe_managed_gguf(Path(directory))
            self.assertFalse(result["available"])
            self.assertTrue(result["independent_of_lm_studio"])

    def test_locally_built_unified_runtime_uses_cli_subcommand(self) -> None:
        self.assertEqual(_runtime_command(Path("shoko-llama.exe")), ["shoko-llama.exe", "cli"])
        self.assertEqual(_runtime_command(Path("llama-cli.exe")), ["llama-cli.exe"])

    def test_locally_built_unified_runtime_uses_server_subcommand(self) -> None:
        self.assertEqual(_server_command(Path("shoko-llama.exe")), ["shoko-llama.exe", "serve"])
        self.assertEqual(_server_command(Path("llama-server.exe")), ["llama-server.exe"])
