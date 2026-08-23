"""Apply predeclared, task-specific checks to a local benchmark report."""

from __future__ import annotations

import json
import os
from pathlib import Path

from verify_generated_outputs import verify_bug_fix, verify_code_generation


def contains(text: str, *needles: str) -> bool:
    lowered = text.lower()
    return all(needle.lower() in lowered for needle in needles)


def audit(task: dict[str, object]) -> dict[str, object]:
    text = str(task.get("output") or "")
    family = str(task["family"])
    checks: dict[str, bool]
    if family == "research":
        checks = {"evidence_a": "Evidence A" in text, "evidence_b": "Evidence B" in text, "limitation": contains(text, "limitation"), "uncertainty": contains(text, "unknown", "not")}
    elif family == "code":
        execution = verify_code_generation(text)
        checks = {"function": "def top_k" in text, "pytest": "pytest" in text, "empty_test": contains(text, "empty", "test"), "boundary": contains(text, "k <= 0"), "execution": bool(execution.get("passed"))}
    elif family == "bug-fix":
        execution = verify_bug_fix(text)
        checks = {"empty_error": contains(text, "ValueError", "empty"), "type_error": contains(text, "TypeError", "non-numeric"), "regression_tests": contains(text, "Regression Tests"), "no_fallback": contains(text, "does not silently"), "execution": bool(execution.get("passed"))}
    elif family == "agentic-rag":
        checks = {"causal_abstention": contains(text, "insufficient evidence"), "sample_identity": "B-17" in text, "exact_source_interval": "[source:lab-notes.md:73-121]" in text, "no_wrong_interval": "[source:lab-notes.md:0-72]" not in text}
    elif family == "reasoning":
        checks = {"answer": contains(text, "38 seconds"), "overlap": contains(text, "6 to 18"), "arithmetic": contains(text, "26 + 12 = 38"), "constraint_check": contains(text, "starts after B")}
    elif family == "online-research":
        checks = {"no_current_claim": contains(text, "cannot", "current factual claim"), "source_plan": contains(text, "source", "search"), "quality_checks": contains(text, "credibility", "currency")}
    else:
        raise ValueError(f"unknown family: {family}")
    return {"id": task["id"], "family": family, "checks": checks, "hits": sum(checks.values()), "total": len(checks), "fraction": sum(checks.values()) / len(checks)}


def main() -> None:
    source = Path(os.environ.get("SHOKO_BENCHMARK_REPORT", str(Path(__file__).with_name("qwen3-4b-complete-output-report.json"))))
    report = json.loads(source.read_text(encoding="utf-8"))
    audited = [audit(task) for task in report["tasks"]]
    output = {"source": str(source), "model": report["model"], "variant": report["variant"], "tasks": audited, "macro_fraction": sum(item["fraction"] for item in audited) / len(audited)}
    destination = source.with_name(source.stem.replace("-report", "-audit") + ".json")
    destination.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
