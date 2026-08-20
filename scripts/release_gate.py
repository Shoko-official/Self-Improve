"""Evidence-based local readiness gate for Frontier releases."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


REQUIRED_FILES = (
    "README.md", "THIRD_PARTY_NOTICES.md", "SBOM.cdx.json", "docs/acceptance-matrix.md", "docs/release-evidence.md",
    ".github/workflows/smoke.yml", ".github/workflows/package.yml", "pnpm-lock.yaml",
    "requirements-build.txt", "src-tauri/Cargo.lock", "src-tauri/Cargo.toml",
    "src-tauri/tauri.release.conf.json", "scripts/build_managed_engine.py",
)
REQUIRED_AREAS = ("Runtime packs", "Science cloud storage", "Multimodal attachments", "Delegation", "Windows package")


def run_gate(root: Path, *, require_clean: bool = True) -> dict[str, object]:
    checks: list[dict[str, object]] = []
    missing = [path for path in REQUIRED_FILES if not (root / path).is_file()]
    checks.append({"name": "required_files", "passed": not missing, "missing": missing})
    matrix = (root / "docs/acceptance-matrix.md").read_text(encoding="utf-8") if (root / "docs/acceptance-matrix.md").is_file() else ""
    missing_areas = [area for area in REQUIRED_AREAS if area not in matrix]
    checks.append({"name": "acceptance_matrix", "passed": not missing_areas, "missing": missing_areas})
    workflow = (root / ".github/workflows/smoke.yml").read_text(encoding="utf-8") if (root / ".github/workflows/smoke.yml").is_file() else ""
    checks.append({"name": "cross_platform_ci", "passed": all(os_name in workflow for os_name in ("ubuntu-latest", "windows-latest", "macos-latest"))})
    package_workflow = (root / ".github/workflows/package.yml").read_text(encoding="utf-8") if (root / ".github/workflows/package.yml").is_file() else ""
    package_targets = ("windows-latest", "ubuntu-latest", "macos-15", "macos-15-intel", "build_managed_engine.py", "--managed-engine-smoke")
    checks.append({"name": "package_workflow", "passed": all(value in package_workflow for value in package_targets)})
    release_config_path = root / "src-tauri/tauri.release.conf.json"
    try:
        release_config = json.loads(release_config_path.read_text(encoding="utf-8"))
        bundle = release_config["bundle"]
        package_contract = bundle["externalBin"] == ["binaries/frontier-engine"] and "../runtime-packs/managed-engine" in bundle["resources"] and "../SBOM.cdx.json" in bundle["resources"]
    except (OSError, KeyError, json.JSONDecodeError):
        package_contract = False
    checks.append({"name": "managed_engine_bundle", "passed": package_contract})
    try:
        sbom = json.loads((root / "SBOM.cdx.json").read_text(encoding="utf-8"))
        properties = {item["name"]: item["value"] for item in sbom["metadata"]["properties"]}
        locks = ("pnpm-lock.yaml", "src-tauri/Cargo.lock", "requirements-build.txt")
        sbom_current = sbom["bomFormat"] == "CycloneDX" and sbom["specVersion"] == "1.6" and len(sbom["components"]) > 100 and all(
            properties.get(f"shoko:lock-sha256:{relative}") == hashlib.sha256((root / relative).read_bytes()).hexdigest() for relative in locks
        )
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        sbom_current = False
    checks.append({"name": "lock_backed_sbom", "passed": sbom_current})
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
