"""Durable execution of capability-gated text generation streams."""

from __future__ import annotations

from collections.abc import Iterator

from .store import FrontierStore


def run_generation(store: FrontierStore, generation_id: str, stream: Iterator[str]) -> Iterator[str]:
    generation = store.generation(generation_id)
    store.claim_job(str(generation["job_id"]))
    chunk_count = 0
    output_chars = 0
    try:
        for chunk in stream:
            if store.job(str(generation["job_id"]))["state"] == "cancel_requested":
                break
            if not isinstance(chunk, str):
                raise TypeError("FR-GENERATION-CHUNK: runtime yielded a non-text chunk")
            store.append_generation_chunk(generation_id, chunk)
            chunk_count += 1
            output_chars += len(chunk)
            yield chunk
        store.complete_job(str(generation["job_id"]), {"chunk_count": chunk_count, "output_chars": output_chars})
    except Exception as error:
        store.fail_job(str(generation["job_id"]), {"code": "FR-GENERATION-STREAM", "detail": str(error)})
        raise
