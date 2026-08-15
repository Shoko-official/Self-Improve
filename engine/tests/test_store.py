import hashlib
import tempfile
import unittest
from pathlib import Path

from frontier_engine.store import ArchivedProjectError, FrontierStore


class FrontierStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = FrontierStore(Path(self.temp_dir.name))

    def tearDown(self) -> None:
        self.store.close()
        self.temp_dir.cleanup()

    def test_versions_keep_payload_and_scientific_provenance(self) -> None:
        project_id = self.store.create_project("RNA QC", "Keep raw inputs immutable.")
        session_id = self.store.create_session(project_id, "Initial analysis", "extended")
        fork_id = self.store.create_session(project_id, "Alternative thresholds", parent_session_id=session_id)
        self.assertNotEqual(session_id, fork_id)
        artifact_id = self.store.create_artifact(project_id, "qc-summary", "text/markdown", session_id)
        first = self.store.add_artifact_version(
            artifact_id,
            b"# QC\nInitial thresholds",
            messages={"session_id": session_id},
            code={"language": "python", "source": "plot_qc()"},
            execution_log={"run_id": "run-1", "exit_code": 0},
            environment={"python": "3.12"},
            inputs={"sample_hash": "abc"},
            review={"status": "unreviewed"},
        )
        second = self.store.add_artifact_version(artifact_id, b"# QC\nRevised thresholds")
        versions = self.store.artifact_versions(artifact_id)
        self.assertEqual([first, second], [1, 2])
        self.assertEqual(versions[0]["execution_log"]["run_id"], "run-1")
        self.assertEqual(versions[0]["content_hash"], hashlib.sha256(b"# QC\nInitial thresholds").hexdigest())
        self.assertTrue((Path(self.temp_dir.name) / str(versions[0]["content_path"])).exists())

    def test_archived_projects_preserve_history_and_reject_writes(self) -> None:
        project_id = self.store.create_project("Archived project")
        self.store.archive_project(project_id)
        with self.assertRaises(ArchivedProjectError):
            self.store.create_session(project_id, "Should not be created")
