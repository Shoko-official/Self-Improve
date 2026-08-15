"""Named scientific environment manifests and truthful local probes."""

from __future__ import annotations

import json
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class EnvironmentManifest:
    name: str
    language: str
    packages: dict[str, str]
    lock_version: int = 1


def save_manifest(root: Path, manifest: EnvironmentManifest) -> Path:
    if not manifest.name.strip() or manifest.language not in {"python", "r"}:
        raise ValueError("Environment name and supported language are required.")
    directory = root / "environments"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{manifest.name}.json"
    if path.exists():
        raise FileExistsError(f"Environment manifest already exists: {manifest.name}")
    path.write_text(json.dumps(asdict(manifest), sort_keys=True), encoding="utf-8")
    return path


def list_manifests(root: Path) -> list[dict[str, object]]:
    directory = root / "environments"
    if not directory.exists(): return []
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(directory.glob("*.json"))]


def probe_environment(language: str) -> dict[str, object]:
    if language == "python":
        return {"language": "python", "available": True, "executable": sys.executable, "version": sys.version.split()[0]}
    executable = shutil.which("Rscript")
    return {"language": "r", "available": executable is not None, "executable": executable, "reason": None if executable else "FR-ENV-R-NOT-FOUND"}
