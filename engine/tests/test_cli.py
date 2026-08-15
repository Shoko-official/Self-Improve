import os
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from frontier_engine.cli import data_root, export_data, import_data, status
from frontier_engine.store import FrontierStore


class CliTests(unittest.TestCase):
    def test_status_initializes_an_empty_local_store(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = status(Path(temp_dir))
        self.assertEqual(result["counts"], {"projects": 0, "sessions": 0, "artifacts": 0, "artifact_versions": 0, "jobs": 0})

    def test_data_root_honors_the_explicit_environment_variable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            previous = os.environ.get("FRONTIER_DATA_DIR")
            os.environ["FRONTIER_DATA_DIR"] = temp_dir
            try:
                self.assertEqual(data_root(), Path(temp_dir))
            finally:
                if previous is None:
                    del os.environ["FRONTIER_DATA_DIR"]
                else:
                    os.environ["FRONTIER_DATA_DIR"] = previous

    def test_export_and_import_preserve_a_local_store(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            source = base / "source"
            store = FrontierStore(source)
            project_id = store.create_project("Transfer")
            artifact_id = store.create_artifact(project_id, "result.txt", "text/plain")
            store.add_artifact_version(artifact_id, b"durable scientific output")
            store.close()
            exported = export_data(source, base / "frontier.zip")
            imported = import_data(base / "frontier.zip", base / "imported")
            self.assertEqual(exported["files"], imported["files"])
            self.assertEqual(status(base / "imported")["counts"]["projects"], 1)
            self.assertTrue((base / "imported" / "content").exists())

    def test_import_rejects_unsafe_archive_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            archive_path = base / "unsafe.zip"
            with ZipFile(archive_path, "w") as archive:
                archive.writestr("frontier-export.json", '{"protocol_version": 1, "files": []}')
                archive.writestr("../outside.txt", "not allowed")
            with self.assertRaisesRegex(ValueError, "unsafe path"):
                import_data(archive_path, base / "destination")
