"""Run a small, auditable local benchmark through Shoko's GGUF runtime."""

from __future__ import annotations

import json
import os
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "engine"))

from frontier_engine.managed_gguf import RUNTIME_VERSION, stream_managed_gguf  # noqa: E402


TASKS = [
    {
        "id": "research-synthesis",
        "family": "research",
        "prompt": """You are evaluating a local research assistant. Synthesize the supplied evidence into a concise answer. Separate observations from inferences, cite the evidence labels exactly, state one limitation, and do not invent missing facts.
Evidence A: The protocol reduced median latency from 220 ms to 160 ms in 30 local trials.
Evidence B: The trials used one Windows host and no held-out workload.
Question: What can be concluded and what remains unknown?""",
        "checks": ["Evidence A", "Evidence B", "unknown", "limitation"],
    },
    {
        "id": "code-generation",
        "family": "code",
        "prompt": """Write a minimal Python function `top_k(values, k)` that returns the k largest values in descending order. State the behavior for k <= 0 and k greater than the input size, then provide three pytest tests including an empty list. Keep the implementation deterministic and avoid external dependencies.""",
        "checks": ["def top_k", "pytest", "empty", "k <= 0"],
    },
    {
        "id": "bug-fix",
        "family": "bug-fix",
        "prompt": """Review this bug: `def average(xs): return sum(xs) / len(xs)` crashes on an empty list and accepts non-numeric values until a confusing error occurs. Propose a small fix, explain the failure mode, and provide regression tests for empty input, valid input, and a non-numeric value. Do not hide errors with a fallback average.""",
        "checks": ["empty", "regression", "non-numeric", "raise"],
    },
    {
        "id": "agentic-rag",
        "family": "agentic-rag",
        "prompt": """Use only the local notes below. Answer the question, include a citation in the form [source:offset], and say 'insufficient evidence' if the notes do not support a claim. Do not use outside knowledge.
[source:lab-notes.md:0-72] The assay was repeated three times. Signal increased after buffer exchange, but no causal control was run.
[source:lab-notes.md:73-121] The sample identity was recorded by barcode B-17.
Question: Is buffer exchange proven to cause the signal increase, and which sample was recorded?""",
        "checks": ["[source:", "insufficient", "B-17", "control"],
    },
    {
        "id": "complex-reasoning",
        "family": "reasoning",
        "prompt": """Solve this explicitly and give a short verification: A pipeline has three stages. Stage A takes 18 seconds and can overlap with B only after its first 6 seconds. Stage B takes 20 seconds. Stage C takes 12 seconds and starts after B. What is the earliest completion time? State the overlap interval and check the arithmetic.""",
        "checks": ["32", "6", "arithmetic"],
    },
    {
        "id": "online-research-discipline",
        "family": "online-research",
        "prompt": """Answer as an online research agent. The current task provides no browser, search tool, URL, or source documents. Explain exactly what is missing, abstain from making a current factual claim, and give a short reproducible search plan with the source quality checks you would apply.""",
        "checks": ["cannot", "source", "search", "current"],
    },
]

MAX_TOKENS = int(os.environ.get("SHOKO_BENCHMARK_MAX_TOKENS", "384"))
VARIANT = os.environ.get("SHOKO_BENCHMARK_VARIANT", "baseline")


def score(text: str, checks: list[str]) -> dict[str, object]:
    lowered = text.lower()
    hits = [item for item in checks if item.lower() in lowered]
    return {"hits": len(hits), "checks": len(checks), "matched": hits, "fraction": len(hits) / len(checks)}


def main() -> None:
    model = Path(os.environ.get("SHOKO_BENCHMARK_MODEL", str(Path.home() / ".lmstudio" / "models" / "lmstudio-community" / "Qwen3-4B-GGUF" / "Qwen3-4B-Q4_K_M.gguf"))).expanduser()
    root = Path.home() / ".frontier-data"
    if not model.is_file():
        raise SystemExit(f"model not found: {model}")
    records: list[dict[str, object]] = []
    for task in TASKS:
        started = time.perf_counter()
        failure: str | None = None
        output = ""
        try:
            output = "".join(stream_managed_gguf(root, model, task["prompt"], max_tokens=MAX_TOKENS))
        except Exception as error:  # benchmark records retain runtime failures
            failure = f"{type(error).__name__}: {error}"
        elapsed = round((time.perf_counter() - started) * 1000, 2)
        record = {"id": task["id"], "family": task["family"], "model": str(model), "runtime": RUNTIME_VERSION, "variant": VARIANT, "max_tokens": MAX_TOKENS, "latency_ms": elapsed, "output": output, "failure": failure}
        if failure is None:
            record["rubric"] = score(output, task["checks"])
        records.append(record)
        print(json.dumps({key: record[key] for key in ("id", "family", "latency_ms", "failure")}, ensure_ascii=False), flush=True)
    report = {"environment": {"os": platform.platform(), "python": platform.python_version(), "runtime": RUNTIME_VERSION}, "model": str(model), "variant": VARIANT, "max_tokens": MAX_TOKENS, "tasks": records}
    destination = Path(__file__).with_name(f"qwen3-4b-{VARIANT}-report.json")
    destination.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(destination)


if __name__ == "__main__":
    main()
