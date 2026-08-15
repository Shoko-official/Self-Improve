import tempfile
import unittest
from pathlib import Path

from frontier_engine.environments import EnvironmentManifest, list_manifests, probe_environment, save_manifest


class EnvironmentTests(unittest.TestCase):
    def test_manifest_is_versioned_and_python_probe_is_truthful(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            save_manifest(Path(directory), EnvironmentManifest("analysis", "python", {"numpy": "1.0"}))
            self.assertEqual(list_manifests(Path(directory))[0]["name"], "analysis")
            self.assertTrue(probe_environment("python")["available"])
