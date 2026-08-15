import tempfile
import unittest
from pathlib import Path

from frontier_engine.environments import EnvironmentManifest, create_python_environment, list_manifests, probe_environment, save_manifest


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
