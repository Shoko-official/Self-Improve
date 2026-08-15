import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from frontier_engine.runtime_install import install_ollama_model
from frontier_engine.runtimes import LocalRuntimeUnavailable
from frontier_engine.store import FrontierStore


class RuntimeInstallTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = FrontierStore(Path(self.temp_dir.name))
        self.project_id = self.store.create_project("Local model")

    def tearDown(self) -> None:
        self.store.close()
        self.temp_dir.cleanup()

    def test_install_records_progress_and_requires_exact_post_pull_probe(self) -> None:
        with patch("frontier_engine.runtime_install.stream_ollama_pull", return_value=iter(["pulling manifest\n", "verifying\n"])), patch("frontier_engine.runtime_install.probe_ollama", return_value={"runtime": "ollama", "available": True, "models": ["qwen3"]}):
            record = install_ollama_model(self.store, self.project_id, "qwen3")
        self.assertEqual(record["state"], "succeeded")
        self.assertEqual(record["result"]["model"], "qwen3")
        self.assertEqual([event["detail"]["output"] for event in self.store.job_events(str(record["id"]))], ["pulling manifest", "verifying"])

    def test_install_fails_when_exact_model_is_not_present_after_pull(self) -> None:
        with patch("frontier_engine.runtime_install.stream_ollama_pull", return_value=iter(["pulling\n"])), patch("frontier_engine.runtime_install.probe_ollama", return_value={"runtime": "ollama", "available": True, "models": ["other"]}):
            record = install_ollama_model(self.store, self.project_id, "qwen3")
        self.assertEqual(record["state"], "failed")
        self.assertEqual(record["diagnostic"]["code"], "FR-RUNTIME-OLLAMA-POST-PULL-VERIFY")

    def test_install_records_a_missing_runtime_as_a_failed_job(self) -> None:
        with patch("frontier_engine.runtime_install.stream_ollama_pull", side_effect=LocalRuntimeUnavailable("FR-RUNTIME-OLLAMA-NOT-FOUND")):
            record = install_ollama_model(self.store, self.project_id, "qwen3")
        self.assertEqual(record["state"], "failed")
        self.assertEqual(record["diagnostic"]["code"], "FR-RUNTIME-OLLAMA-NOT-FOUND")
