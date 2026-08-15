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

    def test_projects_and_sessions_support_configuration_and_literal_search(self) -> None:
        project_id = self.store.create_project("Cell atlas", "Initial scope")
        session_id = self.store.create_session(project_id, "Review batch effects", "extended")
        self.store.set_project_instructions(project_id, "Preserve donor identity.")
        self.store.set_session_reasoning_effort(session_id, "compact")
        result = self.store.search_sessions("batch", project_id)
        self.assertEqual(result[0]["project_name"], "Cell atlas")
        self.assertEqual(result[0]["reasoning_effort"], "compact")
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            self.store.create_session(project_id, "Invalid", "maximum")
        self.store.archive_project(project_id)
        with self.assertRaises(ArchivedProjectError):
            self.store.set_project_instructions(project_id, "Changed")

    def test_project_folder_grants_are_exact_scoped_and_revocable(self) -> None:
        root = Path(self.temp_dir.name)
        project_id = self.store.create_project("Folder scope")
        granted = root / "granted"; granted.mkdir()
        outside = root / "outside"; outside.mkdir()
        grant_id = self.store.grant_project_folder(project_id, granted, "read")
        self.assertEqual(self.store.grant_project_folder(project_id, granted, "read"), grant_id)
        self.assertTrue(self.store.authorize_project_path(project_id, granted / "input.csv", "read"))
        self.assertFalse(self.store.authorize_project_path(project_id, granted / "input.csv", "write"))
        self.assertFalse(self.store.authorize_project_path(project_id, outside / "input.csv", "read"))
        self.store.revoke_project_folder_grant(grant_id)
        self.assertFalse(self.store.authorize_project_path(project_id, granted / "input.csv", "read"))

    def test_artifact_search_returns_latest_durable_version_metadata(self) -> None:
        project_id = self.store.create_project("Artifacts")
        artifact_id = self.store.create_artifact(project_id, "qc-report", "text/markdown")
        self.store.add_artifact_version(artifact_id, b"first")
        self.store.add_artifact_version(artifact_id, b"second")
        self.store.create_artifact(project_id, "qc-plot", "image/svg+xml")
        records = self.store.search_artifacts("QC", project_id, "text/markdown")
        self.assertEqual(records[0]["latest_version"], 2)
        self.assertEqual(records[0]["name"], "qc-report")

    def test_jobs_are_durable_and_cancellation_is_explicit(self) -> None:
        project_id = self.store.create_project("Jobs")
        job_id = self.store.create_job(project_id, "rag.ingest", {"source": "paper.pdf"})
        self.store.close()
        self.store = FrontierStore(Path(self.temp_dir.name))
        self.assertEqual(self.store.job(job_id)["state"], "queued")
        self.assertEqual(self.store.claim_next_job()["state"], "running")
        self.assertEqual(self.store.request_cancellation(job_id)["state"], "cancel_requested")
        self.assertEqual(self.store.complete_job(job_id, {"ignored": True})["state"], "cancelled")
        with self.assertRaises(ValueError):
            self.store.complete_job(job_id, {})

    def test_failed_job_carries_a_diagnostic_record(self) -> None:
        project_id = self.store.create_project("Failures")
        job_id = self.store.create_job(project_id, "model.generate", {})
        self.store.claim_next_job()
        job = self.store.fail_job(job_id, {"code": "FR-MEM-OOM", "evidence": ["allocator refused reservation"]})
        self.assertEqual(job["state"], "failed")
        self.assertEqual(job["diagnostic"]["code"], "FR-MEM-OOM")
