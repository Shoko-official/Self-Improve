"""Durable, cancellable Hugging Face model transfer jobs."""

from __future__ import annotations

import threading
import time
from pathlib import Path

from frontier_engine.model_registry import HuggingFaceHub, HuggingFaceHubError, ModelRegistry
from frontier_engine.store import FrontierStore


MODEL_TRANSFER_OPERATION = "model.huggingface.download"


class _Progress:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._received = 0
        self._total: int | None = None
        self._started = time.monotonic()

    def update(self, received: int, total: int | None) -> None:
        with self._lock:
            self._received = received
            self._total = total

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            received, total = self._received, self._total
        elapsed = max(time.monotonic() - self._started, 0.001)
        return {
            "received_bytes": received,
            "total_bytes": total,
            "percent": round(received * 100 / total, 2) if total else None,
            "bytes_per_second": int(received / elapsed),
        }


def create_model_transfer(store: FrontierStore, hub: HuggingFaceHub, project_id: str, repository_id: str, filename: str, destination: Path, revision: str = "main", expected_sha256: str | None = None) -> dict[str, object]:
    plan = hub.download_plan(repository_id, filename, destination, revision, interactive=True)
    if plan["bytes"] is not None and not plan["fits"]:
        raise HuggingFaceHubError("FR-HF-DISK-SPACE")
    request = {
        "repository_id": repository_id,
        "filename": filename,
        "destination": str(destination.resolve()),
        "revision": revision,
        "expected_sha256": expected_sha256,
        "plan": plan,
    }
    return store.job(store.create_job(project_id, MODEL_TRANSFER_OPERATION, request))


def run_model_transfer(root: Path, job_id: str, hub: HuggingFaceHub | None = None, monitor_interval: float = 0.2) -> dict[str, object]:
    store = FrontierStore(root)
    registry: ModelRegistry | None = None
    progress = _Progress()
    cancel_requested = threading.Event()
    monitor_finished = threading.Event()
    monitor: threading.Thread | None = None
    try:
        registry = ModelRegistry(root / "models.sqlite3")
        job = store.job(job_id)
        if job["operation"] != MODEL_TRANSFER_OPERATION:
            raise ValueError("Job is not a Hugging Face model transfer.")
        request = job["request"]
        store.claim_job(job_id)
        monitor = threading.Thread(
            target=_monitor_transfer,
            args=(root, job_id, progress, cancel_requested, monitor_finished, monitor_interval),
            name=f"model-transfer-{job_id[:8]}",
            daemon=True,
        )
        monitor.start()
        result = registry.download_and_register(
            hub or HuggingFaceHub(),
            str(request["repository_id"]),
            str(request["filename"]),
            Path(str(request["destination"])),
            str(request["revision"]),
            str(request["expected_sha256"]) if request.get("expected_sha256") else None,
            cancel_requested.is_set,
            progress.update,
            lambda: store.job(job_id)["state"] == "running",
        )
        if store.job(job_id)["state"] == "cancel_requested":
            raise HuggingFaceHubError("FR-HF-DOWNLOAD-CANCELLED")
        _finish_monitor(monitor_finished, monitor)
        return store.complete_job(job_id, result)
    except HuggingFaceHubError as error:
        _finish_monitor(monitor_finished, monitor)
        if store.job(job_id)["state"] == "cancel_requested":
            return store.complete_job(job_id, {"cancelled": True})
        return store.fail_job(job_id, {"code": _diagnostic_code(error), "detail": str(error)})
    except Exception as error:
        _finish_monitor(monitor_finished, monitor)
        current = store.job(job_id)
        if current["state"] == "cancel_requested":
            return store.complete_job(job_id, {"cancelled": True})
        if current["state"] == "running":
            return store.fail_job(job_id, {"code": "FR-HF-TRANSFER-WORKER", "detail": str(error)})
        raise
    finally:
        _finish_monitor(monitor_finished, monitor)
        if registry is not None:
            registry.close()
        store.close()


def _monitor_transfer(root: Path, job_id: str, progress: _Progress, cancel_requested: threading.Event, finished: threading.Event, interval: float) -> None:
    store = FrontierStore(root)
    last_received = -1
    try:
        while True:
            current = store.job(job_id)
            if current["state"] == "cancel_requested":
                cancel_requested.set()
            snapshot = progress.snapshot()
            received = int(snapshot["received_bytes"])
            if received != last_received and received > 0 and current["state"] in {"running", "cancel_requested"}:
                store.append_job_event(job_id, "progress", snapshot)
                last_received = received
            if finished.wait(interval):
                break
        current = store.job(job_id)
        snapshot = progress.snapshot()
        if int(snapshot["received_bytes"]) != last_received and int(snapshot["received_bytes"]) > 0 and current["state"] in {"running", "cancel_requested"}:
            store.append_job_event(job_id, "progress", snapshot)
    finally:
        store.close()


def _finish_monitor(finished: threading.Event, monitor: threading.Thread | None) -> None:
    finished.set()
    if monitor is not None and monitor.is_alive() and monitor is not threading.current_thread():
        monitor.join(timeout=2)


def _diagnostic_code(error: Exception) -> str:
    text = str(error)
    if text.startswith("FR-"):
        return text.split(":", 1)[0]
    return "FR-HF-TRANSFER"
