import os
import tempfile
import unittest
from pathlib import Path

from frontier_engine.cli import data_root, status


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
