"""Independently execute Python snippets emitted by the local benchmark."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def python_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    lines = text.splitlines()
    start: int | None = None
    for index, line in enumerate(lines):
        marker = line.strip().lower()
        if start is None and marker in {"```python", "```py"}:
            start = index + 1
        elif start is not None and marker == "```":
            blocks.append("\n".join(lines[start:index]))
            start = None
    return blocks


def verify_code_generation(output: str) -> dict[str, object]:
    blocks = python_blocks(output)
    if not blocks:
        return {"passed": False, "reason": "no-python-block"}
    namespace: dict[str, object] = {}
    exec(blocks[0], namespace)
    top_k = namespace.get("top_k")
    if not callable(top_k):
        return {"passed": False, "reason": "top_k-not-defined"}
    checks = [
        (top_k([], 0), []),
        (top_k([1, 2, 3], -2), []),
        (top_k([1, 2, 3], 5), [3, 2, 1]),
        (top_k([5, 3, 1, 4, 2], 3), [5, 4, 3]),
    ]
    return {"passed": all(actual == expected for actual, expected in checks), "checks": len(checks)}


def verify_bug_fix(output: str) -> dict[str, object]:
    blocks = python_blocks(output)
    if not blocks:
        return {"passed": False, "reason": "no-python-block"}
    namespace: dict[str, object] = {}
    exec(blocks[0], namespace)
    average = namespace.get("average")
    if not callable(average):
        return {"passed": False, "reason": "average-not-defined"}
    if average([1, 2, 3, 4]) != 2.5:
        return {"passed": False, "reason": "valid-case-failed"}
    try:
        average([])
    except ValueError:
        pass
    else:
        return {"passed": False, "reason": "empty-list-did-not-raise-value-error"}
    try:
        average([1, "a", 3])
    except TypeError:
        pass
    else:
        return {"passed": False, "reason": "mixed-list-did-not-raise-type-error"}
    return {"passed": True, "checks": 3}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--model", default="qwen3-4b")
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    tasks = {task["id"]: task for task in report["tasks"]}
    result = {
        "model": args.model,
        "report": str(args.report),
        "code-generation": verify_code_generation(tasks["code-generation"]["output"]),
        "bug-fix": verify_bug_fix(tasks["bug-fix"]["output"]),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if all(item["passed"] for item in result.values() if isinstance(item, dict)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
