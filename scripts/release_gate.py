"""Evidence-based local readiness gate for Frontier releases."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


REQUIRED_FILES = ("README.md", "docs/acceptance-matrix.md", ".github/workflows/smoke.yml", "pnpm-lock.yaml", "src-tauri/Cargo.toml")
REQUIRED_AREAS = ("Runtime packs", "Science cloud storage", "Multimodal attachments", "Delegation")


def run_gate(root: Path, *, require_clean: bool = True) -> dict[str, object]:
    checks: list[dict[str, object]] = []
    missing = [path for path in REQUIRED_FILES if not (root / path).is_file()]
    checks.append({"name": "required_files", "passed": not missing, "missing": missing})
    matrix = (root / "docs/acceptance-matrix.md").read_text(encoding="utf-8") if (root / "docs/acceptance-matrix.md").is_file() else ""
    missing_areas = [area for area in REQUIRED_AREAS if area not in matrix]
    checks.append({"name": "acceptance_matrix", "passed": not missing_areas, "missing": missing_areas})
    workflow = (root / ".github/workflows/smoke.yml").read_text(encoding="utf-8") if (root / ".github/workflows/smoke.yml").is_file() else ""
    checks.append({"name": "cross_platform_ci", "passed": all(os_name in workflow for os_name in ("ubuntu-latest", "windows-latest", "macos-latest"))})
    if require_clean:
        status = subprocess.run(["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True, check=True).stdout
        checks.append({"name": "clean_worktree", "passed": not status.strip(), "detail": status.strip()})
    passed = all(bool(check["passed"]) for check in checks)
    return {"passed": passed, "checks": checks}


def main() -> int:
    parser = argparse.ArgumentParser(prog="frontier-release-gate")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    result = run_gate(args.root.resolve(), require_clean=not args.allow_dirty)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
