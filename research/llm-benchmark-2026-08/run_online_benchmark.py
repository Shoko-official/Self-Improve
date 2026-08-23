"""Run a live-source synthesis task through the same local runtime as the app."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from frontier_engine.managed_gguf import stream_managed_gguf


SOURCES = [
    {
        "title": "Python 3.14.7 Documentation",
        "url": "https://docs.python.org/3.14/",
        "facts": "The official docs page is for Python 3.14.7 and links to What's New in Python 3.14.",
    },
    {
        "title": "Python 3.14.0 Release",
        "url": "https://www.python.org/downloads/release/python-3140/",
        "facts": "Python 3.14.0 is a major release with new features and optimisations; official macOS and Windows binaries include an experimental JIT compiler.",
    },
    {
        "title": "PyPA Dependency Groups Specification",
        "url": "https://packaging.python.org/en/latest/specifications/dependency-groups/",
        "facts": "Dependency groups store package requirements in pyproject.toml without including them in built project metadata. Groups can include other groups.",
    },
]


def main() -> int:
    model = Path(os.environ["SHOKO_BENCHMARK_MODEL"])
    runtime_root = Path.home() / ".frontier-data"
    prompt = """You are evaluating live web research synthesis. Use only the supplied source records.
Answer in four short sections: verified facts, source-specific caveats, practical implication for a Python project, and a confidence note.
Every factual sentence must cite one supplied URL in Markdown. Do not add facts not present in the records.

Source records:
""" + json.dumps(SOURCES, indent=2)
    started = time.perf_counter()
    output = "".join(stream_managed_gguf(runtime_root, model, prompt, max_tokens=512))
    result = {
        "model": str(model),
        "runtime": "shoko-gguf",
        "source_count": len(SOURCES),
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        "sources": SOURCES,
        "output": output,
        "checks": {
            "all_urls_present": all(source["url"] in output for source in SOURCES),
            "caveat_section": "caveat" in output.lower(),
            "confidence_section": "confidence" in output.lower(),
            "no_external_browse_claim": "I cannot browse" not in output,
        },
    }
    destination = Path(__file__).with_name("qwen3-4b-online-live-report.json")
    destination.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
