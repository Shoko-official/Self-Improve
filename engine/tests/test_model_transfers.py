import hashlib
import tempfile
import threading
import time
import unittest
from pathlib import Path

from frontier_engine.model_registry import HuggingFaceHubError
from frontier_engine.model_transfers import create_model_transfer, run_model_transfer
from frontier_engine.store import FrontierStore


class FakeHub:
    payload = b"verified model payload"

    def __init__(self, slow: bool = False) -> None:
        self.slow = slow
        self.started = threading.Event()
        self.interactive: bool | None = None

    def download_plan(self, repository_id: str, filename: str, destination: Path, revision: str, interactive: bool = False) -> dict[str, object]:
        self.interactive = interactive
        return {
            "repository_id": repository_id,
            "filename": filename,
            "destination": str(destination.resolve()),
            "revision": revision,
            "bytes": len(self.payload),
            "required_free_bytes": len(self.payload),
            "free_bytes": len(self.payload) * 10,
            "fits": True,
            "accelerator": "http",
            "interactive": interactive,
        }

    def download_file(self, repository_id: str, filename: str, destination: Path, revision: str, expected_sha256: str | None, cancel_requested, progress, workers: int = 4) -> dict[str, object]:
        self.started.set()
        chunks = 40 if self.slow else 2
        for index in range(chunks):
            if cancel_requested is not None and cancel_requested():
                raise HuggingFaceHubError("FR-HF-DOWNLOAD-CANCELLED")
            if progress is not None:
                progress(min(len(self.payload), index + 1), len(self.payload))
            if self.slow:
                time.sleep(0.01)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(self.payload)
        digest = hashlib.sha256(self.payload).hexdigest()
        return {"repository_id": repository_id, "revision": revision, "filename": filename, "path": str(destination), "bytes": len(self.payload), "sha256": digest, "method": "http", "segments": 1, "resumed_bytes": 0, "elapsed_seconds": 0.01, "bytes_per_second": len(self.payload) * 100}


class ModelTransferTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.store = FrontierStore(self.root)
        self.project_id = self.store.create_project("Model transfer")

    def tearDown(self) -> None:
        self.store.close()
        self.directory.cleanup()

    def test_transfer_records_real_progress_and_unvalidated_registration(self) -> None:
        destination = self.root / "models" / "model.gguf"
        hub = FakeHub()
        queued = create_model_transfer(self.store, hub, self.project_id, "org/model", "model.gguf", destination)
        result = run_model_transfer(self.root, str(queued["id"]), hub, monitor_interval=0.001)
        self.assertTrue(hub.interactive)
        self.assertEqual(result["state"], "succeeded")
        self.assertEqual(result["result"]["model"]["capability_state"], "unvalidated")
        self.assertEqual(result["result"]["transfer"]["sha256"], hashlib.sha256(FakeHub.payload).hexdigest())
        self.assertTrue(any(event["kind"] == "progress" for event in result["events"]))

    def test_transfer_honors_durable_cancellation(self) -> None:
        destination = self.root / "models" / "cancelled.gguf"
        hub = FakeHub(slow=True)
        queued = create_model_transfer(self.store, hub, self.project_id, "org/model", "model.gguf", destination)
        output: list[dict[str, object]] = []
        worker = threading.Thread(target=lambda: output.append(run_model_transfer(self.root, str(queued["id"]), hub, monitor_interval=0.001)))
        worker.start()
        self.assertTrue(hub.started.wait(1))
        self.store.request_cancellation(str(queued["id"]))
        worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(output[0]["state"], "cancelled")
        self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
