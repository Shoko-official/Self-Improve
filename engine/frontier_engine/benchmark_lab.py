"""Auditable local benchmark runs exposed through the desktop app."""

from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Iterator

from .managed_gguf import RUNTIME_VERSION, stream_managed_gguf


TASKS: tuple[dict[str, object], ...] = (
    {
        "id": "research-synthesis",
        "family": "research",
        "prompt": """Synthesize the supplied evidence. Separate observations from inferences, cite Evidence A and Evidence B exactly, state one limitation, and say what is unknown. Do not invent facts.
Evidence A: The protocol reduced median latency from 220 ms to 160 ms in 30 local trials.
Evidence B: The trials used one Windows host and no held-out workload.
Question: What can be concluded and what remains unknown?""",
    },
    {
        "id": "code-generation",
        "family": "code",
        "prompt": """Write a minimal Python function top_k(values, k) returning the k largest values in descending order. State behavior for k <= 0 and k greater than input size. Include three pytest tests, including an empty list. Keep it deterministic and dependency-free.""",
    },
    {
        "id": "bug-fix",
        "family": "bug-fix",
        "prompt": """Fix this bug without hiding errors: def average(xs): return sum(xs) / len(xs). The fix must raise a clear ValueError for empty input and a clear TypeError for non-numeric values. Explain the failure mode and include regression tests for empty, valid, and non-numeric input.""",
    },
    {
        "id": "agentic-rag",
        "family": "agentic-rag",
        "prompt": """Use only these local notes. Answer the question with exact citations. Say 'insufficient evidence' if the notes do not support a causal claim. Do not use outside knowledge.
[source:lab-notes.md:0-72] The assay was repeated three times. Signal increased after buffer exchange, but no causal control was run.
[source:lab-notes.md:73-121] The sample identity was recorded by barcode B-17.
Question: Is buffer exchange proven to cause the signal increase, and which sample was recorded?""",
    },
    {
        "id": "complex-reasoning",
        "family": "reasoning",
        "prompt": """Solve explicitly and verify: Stage A takes 18 seconds. Stage B takes 20 seconds and can overlap with A only after A's first 6 seconds. Stage C takes 12 seconds and starts after B. Give the earliest completion time, the overlap interval, and the arithmetic check.""",
    },
    {
        "id": "online-research-discipline",
        "family": "online-research",
        "prompt": """Act as an online research agent, but no browser, URL, search tool, or source documents are available. Explain what is missing, abstain from current factual claims, and give a reproducible search plan with credibility and currency checks.""",
    },
)


def _contains(text: str, *needles: str) -> bool:
    lowered = text.lower()
    return all(needle.lower() in lowered for needle in needles)


def _fenced_python(text: str) -> str | None:
    match = re.search(r"```(?:python|py)\s*\n(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    return match.group(1) if match else None


def _execute_code(text: str, function_name: str) -> dict[str, object]:
    code = _fenced_python(text)
    if not code:
        return {"passed": False, "reason": "no-python-fence"}
    with tempfile.TemporaryDirectory(prefix="shoko-benchmark-") as directory:
        path = Path(directory) / "candidate.py"
        path.write_text(code, encoding="utf-8")
        check = (
            "import importlib.util\n"
            f"spec=importlib.util.spec_from_file_location('candidate', r'{path}')\n"
            "module=importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(module)\n"
            f"assert callable(getattr(module, '{function_name}'))\n"
            f"fn=getattr(module, '{function_name}')\n"
        )
        if function_name == "top_k":
            check += "assert fn([3, 1, 2], 2) == [3, 2]\nassert fn([], 2) == []\nassert fn([2], 5) == [2]\n"
        else:
            check += "assert fn([1, 3]) == 2\n\n"
        result = subprocess.run([os.environ.get("PYTHON", "python"), "-c", check], capture_output=True, text=True, timeout=10)
        return {"passed": result.returncode == 0, "returncode": result.returncode, "stderr": result.stderr[-500:]}


def audit_task(task_id: str, family: str, text: str) -> dict[str, object]:
    if family == "research":
        checks = {"evidence_a": "Evidence A" in text, "evidence_b": "Evidence B" in text, "limitation": _contains(text, "limitation"), "uncertainty": _contains(text, "unknown", "not")}
    elif family == "code":
        checks = {"function": "def top_k" in text, "pytest": "pytest" in text, "empty_test": _contains(text, "empty", "test"), "boundary": _contains(text, "k <= 0"), "execution": bool(_execute_code(text, "top_k")["passed"])}
    elif family == "bug-fix":
        execution = _execute_code(text, "average")
        checks = {"empty_error": _contains(text, "ValueError", "empty"), "type_error": _contains(text, "TypeError", "non-numeric"), "regression_tests": _contains(text, "test", "empty", "valid"), "no_fallback": not _contains(text, "return 0", "fallback"), "execution": bool(execution["passed"])}
    elif family == "agentic-rag":
        checks = {"causal_abstention": _contains(text, "insufficient evidence") or _contains(text, "not proven"), "sample_identity": "B-17" in text, "exact_source_interval": "[source:lab-notes.md:73-121]" in text, "no_wrong_interval": "[source:lab-notes.md:0-72]" not in text}
    elif family == "reasoning":
        checks = {"answer": _contains(text, "38 seconds"), "overlap": _contains(text, "6 to 18"), "arithmetic": _contains(text, "26 + 12 = 38"), "constraint_check": _contains(text, "starts after B")}
    elif family == "online-research":
        checks = {"no_current_claim": _contains(text, "cannot", "current factual claim"), "source_plan": _contains(text, "source", "search"), "quality_checks": _contains(text, "credibility", "currency")}
    else:
        raise ValueError(f"Unknown benchmark family: {family}")
    return {"id": task_id, "family": family, "checks": checks, "hits": sum(checks.values()), "total": len(checks), "fraction": sum(checks.values()) / len(checks)}


def run_benchmark(root: Path, model: Path, max_tokens: int = 384, variant: str = "desktop") -> dict[str, object]:
    if max_tokens < 64 or max_tokens > 4096:
        raise ValueError("Benchmark token budget must be between 64 and 4096")
    model = model.expanduser().resolve()
    if not model.is_file():
        raise FileNotFoundError(f"Benchmark model not found: {model}")
    started_at = time.time()
    run_id = f"{time.strftime('%Y%m%d-%H%M%S', time.localtime(started_at))}-{uuid.uuid4().hex[:8]}"
    records: list[dict[str, object]] = []
    for task in TASKS:
        started = time.perf_counter()
        output = ""
        failure: str | None = None
        try:
            output = "".join(stream_managed_gguf(root, model, str(task["prompt"]), max_tokens=max_tokens))
        except Exception as error:  # preserve runtime failures in the evidence
            failure = f"{type(error).__name__}: {error}"
        record: dict[str, object] = {"id": task["id"], "family": task["family"], "model": str(model), "runtime": RUNTIME_VERSION, "max_tokens": max_tokens, "latency_ms": round((time.perf_counter() - started) * 1000, 2), "output": output, "failure": failure}
        if failure is None:
            record["rubric"] = audit_task(str(task["id"]), str(task["family"]), output)
        records.append(record)
    completed = all(item["failure"] is None for item in records)
    report: dict[str, object] = {"run_id": run_id, "status": "complete" if completed else "failed", "started_at": started_at, "completed_at": time.time(), "model": str(model), "variant": variant, "max_tokens": max_tokens, "runtime": RUNTIME_VERSION, "environment": {"os": platform.platform(), "python": platform.python_version()}, "tasks": records}
    benchmark_dir = root / "benchmarks"
    benchmark_dir.mkdir(parents=True, exist_ok=True)
    path = benchmark_dir / f"{run_id}.json"
    report["report_path"] = str(path)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def list_benchmark_runs(root: Path) -> dict[str, object]:
    directory = root / "benchmarks"
    reports: list[dict[str, object]] = []
    for path in sorted(directory.glob("*.json"), reverse=True) if directory.is_dir() else ():
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
            reports.append({"run_id": report.get("run_id", path.stem), "status": report.get("status", "unknown"), "model": report.get("model"), "variant": report.get("variant"), "completed_at": report.get("completed_at"), "report_path": str(path), "macro_fraction": sum(float(item.get("rubric", {}).get("fraction", 0)) for item in report.get("tasks", [])) / max(1, sum(1 for item in report.get("tasks", []) if item.get("rubric"))), "latency_ms": sum(float(item.get("latency_ms", 0)) for item in report.get("tasks", []))})
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            continue
    return {"runs": reports}


def load_benchmark_report(root: Path, run_id: str) -> dict[str, object]:
    path = root / "benchmarks" / f"{run_id}.json"
    if not path.is_file():
        raise FileNotFoundError("Benchmark run not found")
    report = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise ValueError("Benchmark report is not an object")
    return report
