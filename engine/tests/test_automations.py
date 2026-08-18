import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from frontier_engine.automations import AutomationStore, pipeline_capabilities, run_pipeline
from frontier_engine.store import FrontierStore


class AutomationTests(unittest.TestCase):
    def test_legacy_dry_run_is_durable_and_external_effects_need_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = AutomationStore(Path(directory) / "automations.sqlite3")
            identifier = store.create("Export", "external publish report")
            self.assertEqual(store.run(identifier).state, "simulated")
            with self.assertRaises(PermissionError):
                store.run(identifier, False)
            self.assertEqual(store.run(identifier, False, True).state, "completed")
            self.assertEqual(len(store.history(identifier)), 2)
            store.close()

    def test_typed_dependency_graph_executes_in_order_and_persists_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = AutomationStore(root / "automations.sqlite3")
            pipeline = store.create_pipeline("project", "Research", [
                {"key": "review", "kind": "skill", "config": {"skill_id": "evidence-review"}},
                {"key": "summary", "kind": "model", "config": {"model": "qwen3", "prompt": "Summarize"}, "depends_on": ["review"]},
            ])
            run = store.queue_run(pipeline["id"], False)
            store.close()
            order = []

            def skill(step, dependencies):
                order.append(step["key"])
                return {"finding_count": 2}

            def model(step, dependencies):
                order.append(step["key"])
                return {"received": dependencies["review"]["finding_count"]}

            result = run_pipeline(root, run["id"], {"skill": skill, "model": model})
            self.assertEqual(result["state"], "succeeded")
            self.assertEqual(order, ["review", "summary"])
            self.assertEqual(result["steps"][1]["output"]["received"], 2)

    def test_step_retry_and_run_retry_keep_attempt_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = AutomationStore(root / "automations.sqlite3")
            pipeline = store.create_pipeline("project", "Retry", [{"key": "review", "kind": "skill", "config": {"skill_id": "evidence-review"}, "max_retries": 1}])
            run = store.queue_run(pipeline["id"], False)
            store.close()
            attempts = 0

            def flaky(step, dependencies):
                nonlocal attempts
                attempts += 1
                if attempts == 1:
                    raise RuntimeError("temporary")
                return {"ok": True}

            result = run_pipeline(root, run["id"], {"skill": flaky})
            self.assertEqual(result["state"], "succeeded")
            self.assertEqual([step["state"] for step in result["steps"]], ["failed", "succeeded"])

    def test_reproducible_kernel_skill_executes_in_the_worker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = AutomationStore(root / "automations.sqlite3")
            pipeline = store.create_pipeline("project", "Kernel", [{"key": "compute", "kind": "skill", "config": {"skill_id": "reproducible-kernel", "code": "print(6 * 7)"}}])
            run = store.queue_run(pipeline["id"], False)
            store.close()
            result = run_pipeline(root, run["id"])
            self.assertEqual(result["state"], "succeeded")
            self.assertEqual(result["steps"][0]["output"]["stdout"], "42\n")

    def test_cancellation_and_manual_retry_are_durable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = AutomationStore(Path(directory) / "automations.sqlite3")
            pipeline = store.create_pipeline("project", "Cancel", [{"key": "review", "kind": "skill", "config": {"skill_id": "evidence-review"}}])
            first = store.queue_run(pipeline["id"], False)
            cancelled = store.request_cancellation(first["id"])
            retry = store.retry_run(cancelled["id"])
            self.assertEqual(cancelled["state"], "cancelled")
            self.assertEqual(retry["parent_run_id"], first["id"])
            self.assertEqual(retry["trigger_kind"], "retry")
            store.close()

    def test_external_connector_requires_approval_and_unavailable_items_are_hidden(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = AutomationStore(Path(directory) / "automations.sqlite3")
            pipeline = store.create_pipeline("project", "Catalog", [{"key": "search", "kind": "connector", "config": {"connector_id": "huggingface-model-catalog", "query": "biology"}}])
            self.assertTrue(pipeline["external_effects"])
            with self.assertRaises(PermissionError):
                store.queue_run(pipeline["id"], False)
            approved = store.queue_run(pipeline["id"], False, True)
            self.assertTrue(approved["external_approved"])
            cancelled = store.request_cancellation(approved["id"])
            with self.assertRaises(PermissionError):
                store.retry_run(cancelled["id"])
            retried = store.retry_run(cancelled["id"], True)
            self.assertTrue(retried["external_approved"])
            with self.assertRaisesRegex(ValueError, "UNAVAILABLE"):
                store.create_pipeline("project", "Unavailable", [{"key": "send", "kind": "connector", "config": {"connector_id": "not-connected"}}])
            self.assertNotIn("not-connected", {item["id"] for item in pipeline_capabilities()["connectors"]})
            store.close()

    def test_interval_schedule_exposes_only_due_pipelines(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = AutomationStore(Path(directory) / "automations.sqlite3")
            pipeline = store.create_pipeline("project", "Scheduled", [{"key": "review", "kind": "skill", "config": {"skill_id": "evidence-review"}}], {"kind": "interval", "interval_seconds": 60})
            before = datetime.now(UTC).isoformat()
            after = (datetime.now(UTC) + timedelta(seconds=61)).isoformat()
            self.assertEqual(store.due_pipelines(before), [])
            self.assertEqual(store.due_pipelines(after)[0]["id"], pipeline["id"])
            original_due_at = store.pipeline(pipeline["id"])["next_due_at"]
            store.queue_run(pipeline["id"], True)
            self.assertEqual(store.pipeline(pipeline["id"])["next_due_at"], original_due_at)
            first = store.queue_due_run(pipeline["id"], after)
            second = store.queue_due_run(pipeline["id"], after)
            self.assertEqual(first["trigger_kind"], "schedule")
            self.assertIsNone(second)
            store.close()

    def test_pipeline_input_shapes_and_external_query_are_validated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = AutomationStore(Path(directory) / "automations.sqlite3")
            with self.assertRaisesRegex(ValueError, "must be a list"):
                store.create_pipeline("project", "Invalid", {"key": "one"})
            with self.assertRaisesRegex(ValueError, "require a query"):
                store.create_pipeline("project", "Invalid query", [{"key": "search", "kind": "connector", "config": {"connector_id": "huggingface-model-catalog"}}])
            store.close()

    def test_cycle_is_rejected_before_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = AutomationStore(Path(directory) / "automations.sqlite3")
            with self.assertRaisesRegex(ValueError, "cycle"):
                store.create_pipeline("project", "Cycle", [
                    {"key": "one", "kind": "skill", "config": {"skill_id": "evidence-review"}, "depends_on": ["two"]},
                    {"key": "two", "kind": "skill", "config": {"skill_id": "evidence-review"}, "depends_on": ["one"]},
                ])
            store.close()

    def test_cli_creates_and_dry_runs_a_typed_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            frontier = FrontierStore(root)
            project_id = frontier.create_project("Automation CLI")
            frontier.close()
            environment = {**os.environ, "PYTHONPATH": str(Path(__file__).parents[1])}
            steps = json.dumps([{"key": "review", "kind": "skill", "config": {"skill_id": "evidence-review"}}])
            created = subprocess.run([sys.executable, "-m", "frontier_engine.cli", "create-automation", "--project-id", project_id, "--name", "Review", "--steps-json", steps, "--data-dir", str(root), "--json"], capture_output=True, check=True, env=environment, text=True)
            automation_id = json.loads(created.stdout)["id"]
            simulated = subprocess.run([sys.executable, "-m", "frontier_engine.cli", "automation-start", "--automation-id", automation_id, "--data-dir", str(root), "--json"], capture_output=True, check=True, env=environment, text=True)
            self.assertEqual(json.loads(simulated.stdout)["state"], "simulated")


if __name__ == "__main__":
    unittest.main()
