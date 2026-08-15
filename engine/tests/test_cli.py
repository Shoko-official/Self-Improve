import os
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from frontier_engine.cli import archive_project, artifact_versions, artifacts, cancel_job, claims, create_artifact, create_claim, create_project, create_session, data_root, download_huggingface_model, enqueue_job, export_data, generate_local, generations, grant_project_folder, import_data, jobs, project_folders, projects, revoke_project_folder, search_artifacts, search_huggingface_models, search_sessions, sessions, set_claim_status, set_project_instructions, set_session_reasoning_effort, set_session_starred, status
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

    def test_projects_and_sessions_support_configuration_and_search(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = create_project(root, "Discovery", "Initial scope")
            session = create_session(root, project["id"], "Review notebooks", reasoning_effort="extended")
            set_project_instructions(root, project["id"], "Keep raw records.")
            set_session_reasoning_effort(root, session["id"], "compact")
            found = search_sessions(root, "notebooks", project["id"])["sessions"]
            self.assertEqual(found[0]["reasoning_effort"], "compact")

    def test_projects_can_grant_and_revoke_local_folders(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir); project = create_project(root, "Folder scope")
            folder = root / "fixture"; folder.mkdir()
            grant = grant_project_folder(root, project["id"], folder, "read")
            self.assertEqual(project_folders(root, project["id"])["grants"][0]["path"], str(folder.resolve()))
            self.assertTrue(revoke_project_folder(root, grant["id"])["revoked"])

    def test_jobs_can_be_enqueued_listed_and_cancelled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project_id = create_project(root, "Jobs")['id']
            job = enqueue_job(root, project_id, "rag.ingest")
            self.assertEqual(jobs(root)["jobs"][0]["state"], "queued")
            self.assertEqual(cancel_job(root, job["id"])["state"], "cancelled")

    def test_generations_are_listed_and_unsupported_runtime_is_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project_id = create_project(root, "Generations")["id"]
            record = generate_local(root, project_id, "unknown", "model", "prompt")
            self.assertEqual(record["state"], "failed")
            self.assertEqual(record["diagnostic"]["code"], "FR-GENERATION-RUNTIME")
            self.assertEqual(generations(root, project_id)["generations"][0]["id"], record["id"])

    def test_huggingface_commands_keep_network_transfer_explicit(self) -> None:
        with patch("frontier_engine.cli.HuggingFaceHub") as hub_type:
            hub_type.return_value.search_models.return_value = [{"modelId": "org/model"}]
            self.assertEqual(search_huggingface_models("model")["models"][0]["modelId"], "org/model")

    def test_artifacts_keep_versions_and_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project_id = create_project(root, "Artifacts")["id"]
            artifact = create_artifact(root, project_id, "result.md", "text/markdown", "# Result")
            self.assertEqual(artifacts(root, project_id)["artifacts"][0]["name"], "result.md")
            self.assertEqual(artifact_versions(root, artifact["id"])["versions"][0]["execution_log"]["state"], "not_executed")

    def test_artifacts_are_searchable_by_literal_name_and_media_type(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir); project_id = create_project(root, "Artifacts")["id"]
            create_artifact(root, project_id, "qc-report.md", "text/markdown", "# QC")
            self.assertEqual(search_artifacts(root, "QC", project_id, "text/markdown")["artifacts"][0]["name"], "qc-report.md")

    def test_claims_keep_evidence_and_support_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            claim = create_claim(root, "inference", "Candidate improved recall", "Fixture dataset only.", [("artifact://benchmark", "row:4")])
            set_claim_status(root, claim["id"], "supported")
            record = claims(root)["claims"][0]
            self.assertEqual(record["status"], "supported")
            self.assertEqual(record["evidence"][0]["evidence_uri"], "artifact://benchmark")

    def test_serve_prints_an_ephemeral_loopback_descriptor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            environment = {**os.environ, "FRONTIER_DATA_DIR": temp_dir}
            result = subprocess.run([sys.executable, "-m", "frontier_engine.cli", "serve", "--duration-seconds", "0", "--json"], capture_output=True, check=True, env=environment, text=True)
            descriptor = json.loads(result.stdout)
            self.assertTrue(descriptor["url"].startswith("http://127.0.0.1:"))
            self.assertEqual(descriptor["status_path"], "/status")
            self.assertTrue(descriptor["token"])

    def test_background_control_plane_has_no_persisted_bearer_token(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            environment = {**os.environ, "FRONTIER_DATA_DIR": str(root)}
            def control(*arguments: str) -> dict[str, object]:
                result = subprocess.run([sys.executable, "-m", "frontier_engine.cli", *arguments, "--json"], capture_output=True, check=True, env=environment, text=True)
                return json.loads(result.stdout)
            subprocess.run([sys.executable, "-m", "frontier_engine.cli", "serve", "--background", "--json"], check=True, env=environment, stdout=subprocess.DEVNULL)
            service = control("service-status")
            try:
                self.assertTrue(service["running"])
                self.assertTrue(str(service["url"]).startswith("http://127.0.0.1:"))
                state = (root / "control-plane-service.json").read_text()
                self.assertNotIn("token", state)
                self.assertEqual(control("url")["url"], service["url"])
                self.assertTrue(control("service-status")["running"])
                self.assertNotIn("token", "\n".join(control("logs", "--tail", "10")["lines"]))
            finally:
                self.assertFalse(control("stop")["running"])
