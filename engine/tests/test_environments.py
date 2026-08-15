import tempfile
import unittest
import json
from unittest.mock import patch
from pathlib import Path

from frontier_engine.environments import EnvironmentManifest, create_python_environment, install_python_packages, list_manifests, probe_environment, save_manifest


class EnvironmentTests(unittest.TestCase):
    def test_manifest_is_versioned_and_python_probe_is_truthful(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            save_manifest(Path(directory), EnvironmentManifest("analysis", "python", {"numpy": "1.0"}))
            self.assertEqual(list_manifests(Path(directory))[0]["name"], "analysis")
            self.assertTrue(probe_environment("python")["available"])

    def test_creates_an_isolated_python_environment_without_packages_or_network(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            environment = create_python_environment(root, "analysis")
            self.assertTrue(Path(str(environment["executable"])).is_file())
            self.assertEqual(environment["packages"], {})
            self.assertEqual(len(str(environment["package_fingerprint"])), 64)
            self.assertEqual(list_manifests(root)[0]["name"], "analysis")
            with self.assertRaises(FileExistsError):
                create_python_environment(root, "analysis")
            with self.assertRaises(ValueError):
                create_python_environment(root, "../outside")

    def test_installs_packages_and_updates_manifest_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = EnvironmentManifest("analysis", "python", {}, executable="python", package_fingerprint="empty")
            save_manifest(root, manifest)
            responses = [
                type("Result", (), {"returncode": 1, "stdout": "", "stderr": "missing"})(),
                type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})(),
                type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})(),
                type("Result", (), {"returncode": 0, "stdout": json.dumps([{"name": "numpy", "version": "2.0"}]), "stderr": ""})(),
            ]
            with patch("frontier_engine.environments.subprocess.run", side_effect=responses):
                updated = install_python_packages(root, "analysis", ["numpy==2.0"])
            self.assertEqual(updated["packages"], {"numpy": "2.0"})
            self.assertNotEqual(updated["package_fingerprint"], "empty")
            with self.assertRaises(ValueError): install_python_packages(root, "analysis", ["--index-url", "https://example.invalid"])
