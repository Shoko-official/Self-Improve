"""Explicit, durable installation operations for local runtimes."""

from __future__ import annotations

from frontier_engine.runtimes import LocalRuntimeUnavailable, probe_ollama, stream_ollama_pull
from frontier_engine.store import FrontierStore


def install_ollama_model(store: FrontierStore, project_id: str, model: str) -> dict[str, object]:
    """Pull one requested model, preserve progress, and verify its exact identity."""
    model = model.strip()
    if not model:
        raise ValueError("An Ollama model identifier is required.")
    job_id = store.create_job(project_id, "runtime.ollama.pull", {"runtime": "ollama", "model": model})
    store.claim_job(job_id)
    try:
        for output in stream_ollama_pull(model):
            store.append_job_event(job_id, "progress", {"output": output.rstrip("\r\n")})
        probe = probe_ollama()
        if model not in probe.get("models", []):
            store.fail_job(job_id, {"code": "FR-RUNTIME-OLLAMA-POST-PULL-VERIFY", "model": model, "probe": probe})
        else:
            store.complete_job(job_id, {"runtime": "ollama", "model": model, "probe": probe})
    except LocalRuntimeUnavailable as error:
        store.fail_job(job_id, {"code": str(error), "model": model})
    except Exception as error:
        store.fail_job(job_id, {"code": "FR-RUNTIME-OLLAMA-PULL-FAILED", "model": model, "detail": str(error)})
    return store.job(job_id)
