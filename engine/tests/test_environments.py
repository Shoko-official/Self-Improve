import tempfile
import unittest
import json
from unittest.mock import patch
from pathlib import Path

from frontier_engine.environments import EnvironmentManifest, create_python_environment, create_r_environment, install_python_packages, install_r_packages, list_manifests, probe_environment, save_manifest


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

    def test_r_environment_is_truthful_when_runtime_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch("frontier_engine.environments.shutil.which", return_value=None):
                with self.assertRaisesRegex(RuntimeError, "FR-ENV-R-NOT-FOUND"): create_r_environment(Path(directory), "analysis")

    def test_installs_r_packages_and_updates_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); library = root / "r-library"; library.mkdir()
            save_manifest(root, EnvironmentManifest("analysis", "r", {}, path=str(library), executable="Rscript", runtime_version="R 4.4", package_fingerprint="empty"))
            result = type("Result", (), {"returncode": 0, "stdout": "Package\tVersion\nrjson\t1.0\n", "stderr": ""})()
            with patch("frontier_engine.environments.subprocess.run", return_value=result) as run:
                updated = install_r_packages(root, "analysis", ["rjson"])
            self.assertEqual(updated["packages"], {"rjson": "1.0"})
            self.assertEqual(run.call_args.kwargs["env"]["R_LIBS_USER"], str(library))
            self.assertIn("install.packages", run.call_args.args[0][-1])
            with patch("frontier_engine.environments.subprocess.run", return_value=result) as bioc_run:
                install_r_packages(root, "analysis", ["GenomicRanges"], channel="bioconductor")
            self.assertIn("BiocManager::install", bioc_run.call_args.args[0][-1])
            self.assertIn("ask=FALSE", bioc_run.call_args.args[0][-1])
            with self.assertRaises(ValueError): install_r_packages(root, "analysis", ["rjson"], "http://insecure.invalid")
            with self.assertRaises(ValueError): install_r_packages(root, "analysis", ["rjson"], channel="unknown")
