import os
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from frontier_engine.cli import acknowledge_notification, agent_activity, annotations, archive_project, artifact_versions, artifacts, cancel_job, claims, consume_annotations, create_annotation, create_artifact, create_claim, create_project, create_session, data_root, download_huggingface_model, enqueue_job, execute_shell, export_data, generate_local, generations, grant_project_folder, huggingface_model_transfer, import_data, install_ollama_model, jobs, local_model_catalog, manage_goal, manage_todo, pending_notifications, plan_huggingface_model_download, project_folders, project_git_context, projects, reference_lm_studio_model, retry_huggingface_model_transfer, retry_job, review_scientific_claims, revoke_project_folder, run_agent, search_artifacts, search_huggingface_models, search_sessions, sessions, set_claim_status, set_project_instructions, set_session_reasoning_effort, set_session_starred, start_huggingface_model_transfer, status, workspace_tool
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

    def test_project_git_context_reports_branch_and_worktree_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "state"
            repository = Path(temp_dir) / "repository"
            repository.mkdir()
            subprocess.run(["git", "init", "-b", "main", str(repository)], check=True, capture_output=True)
            (repository / "note.txt").write_text("untracked", encoding="utf-8")
            project = create_project(root, "Git")
            self.assertFalse(project_git_context(root, project["id"])["linked"])
            grant_project_folder(root, project["id"], repository, "read")
            context = project_git_context(root, project["id"])
            self.assertTrue(context["repository"])
            self.assertEqual(context["branch"], "main")
            self.assertEqual(context["changes"], 1)
            self.assertFalse(context["ci"]["available"])

    def test_jobs_can_be_enqueued_listed_and_cancelled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project_id = create_project(root, "Jobs")['id']
            job = enqueue_job(root, project_id, "rag.ingest")
            self.assertEqual(jobs(root)["jobs"][0]["state"], "queued")
            self.assertEqual(cancel_job(root, job["id"])["state"], "cancelled")

    def test_cancelled_jobs_can_be_retried_without_mutating_the_first_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir); project_id = create_project(root, "Jobs")["id"]
            first = enqueue_job(root, project_id, "rag.ingest")
            cancel_job(root, first["id"])
            retry = retry_job(root, first["id"])
            self.assertEqual(retry["parent_job_id"], first["id"])
            self.assertEqual(retry["state"], "queued")

    def test_generations_are_listed_and_unsupported_runtime_is_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project_id = create_project(root, "Generations")["id"]
            record = generate_local(root, project_id, "unknown", "model", "prompt")
            self.assertEqual(record["state"], "failed")
            self.assertEqual(record["diagnostic"]["code"], "FR-GENERATION-RUNTIME")
            self.assertEqual(generations(root, project_id)["generations"][0]["id"], record["id"])

    def test_ollama_install_command_returns_its_durable_job_record(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); project_id = create_project(root, "Runtime")["id"]
            with patch("frontier_engine.cli.install_local_ollama_model", return_value={"id": "job", "state": "failed", "events": []}) as install:
                record = install_ollama_model(root, project_id, "qwen3")
            install.assert_called_once()
            self.assertEqual(record["state"], "failed")

    def test_lm_studio_library_is_referenced_without_copy_or_runtime_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model = root / "library" / "model.gguf"
            model.parent.mkdir()
            model.write_bytes(b"gguf")
            library = {"available": True, "models_root": str(model.parent), "models": [{"path": str(model)}]}
            with patch("frontier_engine.cli.probe_lm_studio_library", return_value=library), patch("frontier_engine.cli.probe_ollama", return_value={"available": False, "models": []}):
                self.assertEqual(local_model_catalog()["lm_studio_library"], library)
                result = reference_lm_studio_model(root, model)
            self.assertFalse(result["copied"])
            self.assertEqual(result["source"], "lmstudio-library")
            self.assertEqual(result["model"]["path"], str(model.resolve()))
            self.assertEqual(list(root.rglob("*.gguf")), [model])

    def test_huggingface_commands_keep_network_transfer_explicit(self) -> None:
        with patch("frontier_engine.cli.HuggingFaceHub") as hub_type:
            hub_type.return_value.search_models.return_value = [{"modelId": "org/model"}]
            hub_type.return_value.download_plan.return_value = {"bytes": 42, "fits": True}
            self.assertEqual(search_huggingface_models("model")["models"][0]["modelId"], "org/model")
            self.assertTrue(plan_huggingface_model_download("org/model", "model.gguf", Path("model.gguf"))["plan"]["fits"])

    def test_huggingface_transfer_start_status_and_retry_are_durable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project_id = create_project(root, "Transfer")["id"]
            plan = {"bytes": 42, "fits": True, "accelerator": "parallel-http"}
            with patch("frontier_engine.cli.HuggingFaceHub") as hub_type, patch("frontier_engine.cli._spawn_model_transfer_worker", return_value=123) as spawn:
                hub_type.return_value.download_plan.return_value = plan
                queued = start_huggingface_model_transfer(root, project_id, "org/model", "model.gguf", root / "model.gguf")
                self.assertEqual(queued["state"], "queued")
                self.assertEqual(huggingface_model_transfer(root, queued["id"])["request"]["plan"], plan)
                status_result = subprocess.run([sys.executable, "-m", "frontier_engine.cli", "model-download-status", "--job-id", queued["id"], "--data-dir", str(root), "--json"], capture_output=True, check=True, text=True)
                self.assertEqual(json.loads(status_result.stdout)["id"], queued["id"])
                store = FrontierStore(root)
                try:
                    store.claim_job(queued["id"])
                    store.fail_job(queued["id"], {"code": "fixture"})
                finally:
                    store.close()
                retry = retry_huggingface_model_transfer(root, queued["id"])
                self.assertEqual(retry["parent_job_id"], queued["id"])
                self.assertEqual(spawn.call_count, 2)

    def test_connector_and_skill_catalogs_are_available_to_desktop_clients(self) -> None:
        connectors = subprocess.run([sys.executable, "-m", "frontier_engine.cli", "connectors", "--json"], capture_output=True, check=True, text=True)
        skills = subprocess.run([sys.executable, "-m", "frontier_engine.cli", "skills", "--json"], capture_output=True, check=True, text=True)
        self.assertTrue(json.loads(connectors.stdout)["connectors"])
        self.assertTrue(json.loads(skills.stdout)["skills"])

    def test_extension_catalog_hides_unexecutable_extensions(self) -> None:
        extensions = subprocess.run([sys.executable, "-m", "frontier_engine.cli", "extensions", "--json"], capture_output=True, check=True, text=True)
        records = json.loads(extensions.stdout)["extensions"]
        self.assertTrue(all(record["availability"] == "installed-and-loadable" and record["skill_ids"] for record in records))

    def test_create_environment_command_creates_a_real_local_python_environment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, "-m", "frontier_engine.cli", "create-environment", "--name", "analysis", "--data-dir", directory, "--json"], capture_output=True, check=True, text=True)
            record = json.loads(result.stdout)
            self.assertEqual(record["name"], "analysis")
            self.assertTrue(Path(record["executable"]).is_file())

    def test_shell_command_requires_existing_project_folder_grant(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "state"; workspace = Path(directory) / "workspace"; workspace.mkdir()
            project_id = create_project(root, "Shell")["id"]
            grant_project_folder(root, project_id, workspace, "write")
            result = execute_shell(root, project_id, workspace, [sys.executable, "-c", "print('shell')"], 5)
            self.assertEqual(result["result"]["stdout"], "shell\n")

    def test_agent_workspace_command_obeys_read_and_write_grants(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "state"; workspace = Path(directory) / "workspace"; workspace.mkdir()
            project_id = create_project(root, "Agent")["id"]
            grant_project_folder(root, project_id, workspace, "write")
            self.assertEqual(workspace_tool(root, project_id, workspace, "write", "note.txt", "agent note")["path"], "note.txt")
            grant_project_folder(root, project_id, workspace, "read")
            self.assertEqual(workspace_tool(root, project_id, workspace, "read", "note.txt")["content"], "agent note")

    def test_agent_activity_is_project_scoped_and_preserves_a_runtime_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); project_id = create_project(root, "Agent") ["id"]
            with patch("frontier_engine.agent_runner.stream_ollama", side_effect=RuntimeError("FR-RUNTIME-OLLAMA-NOT-FOUND")):
                with self.assertRaisesRegex(RuntimeError, "FR-RUNTIME-OLLAMA-NOT-FOUND"):
                    run_agent(root, project_id, "qwen3", "Summarize the fixture")
            activity = agent_activity(root, project_id)
            self.assertEqual(activity["todos"][0]["state"], "failed")
            self.assertEqual(activity["tool_calls"][0]["state"], "failed")
            archive_project(root, project_id)
            with self.assertRaisesRegex(Exception, "(?i)project"):
                agent_activity(root, project_id)

    def test_agent_activity_manages_goal_and_todo_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); project_id = create_project(root, "Agent") ["id"]
            from frontier_engine.agent_state import AgentStateStore
            state = AgentStateStore(root / "agent.sqlite3"); state.set_plan(project_id, "Draft protocol"); todo_id = state.add_todo(project_id, "Read source"); state.close()
            self.assertEqual(manage_goal(root, project_id, "goal-paused")["plan_state"], "paused")
            self.assertEqual(manage_goal(root, project_id, "goal-update", "Review protocol")["plan"], "Review protocol")
            self.assertEqual(manage_todo(root, project_id, todo_id, "update", "Review source")["todos"][0]["text"], "Review source")
            self.assertIsNone(manage_goal(root, project_id, "goal-delete")["plan"])

    def test_notification_listing_and_acknowledgement_are_durable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            from frontier_engine.notifications import NotificationStore
            store = NotificationStore(root / "notifications.sqlite3"); identifier = store.create("job/run", "warning", "Review", "A model needs approval", "frontier://jobs/run"); store.close()
            self.assertEqual(pending_notifications(root)["notifications"][0]["id"], identifier)
            self.assertEqual(acknowledge_notification(root, identifier)["notifications"], [])

    def test_artifacts_keep_versions_and_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project_id = create_project(root, "Artifacts")["id"]
            markdown = "# Result\n\n- [x] verified\n\n| metric | value |\n| --- | ---: |\n| score | 42 |"
            artifact = create_artifact(root, project_id, "result.md", "text/markdown", markdown)
            self.assertEqual(artifacts(root, project_id)["artifacts"][0]["name"], "result.md")
            versioned_artifact = artifact_versions(root, artifact["id"])
            self.assertEqual(versioned_artifact["versions"][0]["execution_log"]["state"], "not_executed")
            self.assertEqual(versioned_artifact["preview"]["artifact_version_id"], versioned_artifact["versions"][0]["id"])
            self.assertEqual(versioned_artifact["preview"]["renderer_id"], "markdown.basic")
            self.assertEqual(versioned_artifact["preview"]["markdown"], markdown)

    def test_annotations_require_an_exact_artifact_version_and_consume_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); project_id = create_project(root, "Annotations")["id"]; artifact = create_artifact(root, project_id, "result.md", "text/markdown", "# Result")
            version_id = artifact_versions(root, artifact["id"])["versions"][0]["id"]
            created = create_annotation(root, version_id, "markdown", '{"offset": 2}', "Clarify this result")
            self.assertEqual(annotations(root, version_id)["annotations"][0]["id"], created["id"])
            self.assertEqual(consume_annotations(root, (created["id"],))["annotations"][0]["body"], "Clarify this result")
            with self.assertRaises(ValueError): consume_annotations(root, (created["id"],))
            with self.assertRaises(KeyError): create_annotation(root, "missing-version", "text", "{}", "No target")

    def test_reviewer_cli_returns_evidence_gap_findings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); create_claim(root, "computed", "Mean was 4", "Fixture only", [])
            self.assertEqual(review_scientific_claims(root)["findings"][0]["code"], "FR-REVIEW-UNTRACEABLE-COMPUTATION")

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
