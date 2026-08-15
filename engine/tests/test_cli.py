import os
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from frontier_engine.cli import archive_project, artifact_versions, artifacts, cancel_job, create_artifact, create_project, create_session, data_root, enqueue_job, export_data, import_data, jobs, projects, sessions, set_session_starred, status
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

    def test_projects_can_be_listed_and_created(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            created = create_project(root, "Local research")
            self.assertEqual(created["name"], "Local research")
            self.assertEqual([record["name"] for record in projects(root)["projects"]], ["Local research"])
            with self.assertRaisesRegex(ValueError, "required"):
                create_project(root, "   ")

    def test_sessions_can_be_created_forked_starred_and_archived(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project_id = create_project(root, "Sessions")["id"]
            first = create_session(root, project_id, "Initial analysis")
            fork = create_session(root, project_id, "Alternative", first["id"])
            set_session_starred(root, fork["id"], True)
            records = sessions(root, project_id)["sessions"]
            self.assertEqual([record["parent_session_id"] for record in records], [None, first["id"]])
            self.assertEqual(records[1]["starred"], 1)
            archive_project(root, project_id)
            with self.assertRaisesRegex(Exception, "archived"):
                create_session(root, project_id, "Blocked")

    def test_jobs_can_be_enqueued_listed_and_cancelled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project_id = create_project(root, "Jobs")['id']
            job = enqueue_job(root, project_id, "rag.ingest")
            self.assertEqual(jobs(root)["jobs"][0]["state"], "queued")
            self.assertEqual(cancel_job(root, job["id"])["state"], "cancelled")

    def test_artifacts_keep_versions_and_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project_id = create_project(root, "Artifacts")["id"]
            artifact = create_artifact(root, project_id, "result.md", "text/markdown", "# Result")
            self.assertEqual(artifacts(root, project_id)["artifacts"][0]["name"], "result.md")
            self.assertEqual(artifact_versions(root, artifact["id"])["versions"][0]["execution_log"]["state"], "not_executed")
