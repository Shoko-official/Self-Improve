"""Durable execution of capability-gated text generation streams."""

from __future__ import annotations

import time
from collections.abc import Iterator

from .store import FrontierStore


def run_generation(store: FrontierStore, generation_id: str, stream: Iterator[str]) -> Iterator[str]:
    generation = store.generation(generation_id)
    store.claim_job(str(generation["job_id"]))
    chunk_count = 0
    output_chars = 0
    started = time.monotonic()
    first_chunk_seconds: float | None = None
    try:
        for chunk in stream:
            if store.job(str(generation["job_id"]))["state"] == "cancel_requested":
                break
            if not isinstance(chunk, str):
                raise TypeError("FR-GENERATION-CHUNK: runtime yielded a non-text chunk")
            if first_chunk_seconds is None:
                first_chunk_seconds = time.monotonic() - started
            store.append_generation_chunk(generation_id, chunk)
            chunk_count += 1
            output_chars += len(chunk)
            yield chunk
        result: dict[str, object] = {"chunk_count": chunk_count, "output_chars": output_chars, "wall_seconds": time.monotonic() - started, "time_to_first_chunk_seconds": first_chunk_seconds}
        runtime_metrics = getattr(stream, "metrics", None)
        if isinstance(runtime_metrics, dict):
            result["runtime_metrics"] = runtime_metrics
        store.complete_job(str(generation["job_id"]), result)
    except Exception as error:
        store.fail_job(str(generation["job_id"]), {"code": "FR-GENERATION-STREAM", "detail": str(error)})
        raise
