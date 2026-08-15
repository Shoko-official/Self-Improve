"""Named scientific environment manifests and truthful local probes."""

from __future__ import annotations

import json
import hashlib
import shutil
import subprocess
import sys
import re
import venv
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class EnvironmentManifest:
    name: str
    language: str
    packages: dict[str, str]
    lock_version: int = 1
    path: str | None = None
    executable: str | None = None
    python_version: str | None = None
    package_fingerprint: str | None = None
    created_at: str | None = None


def save_manifest(root: Path, manifest: EnvironmentManifest) -> Path:
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", manifest.name) or manifest.language not in {"python", "r"}:
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


def create_python_environment(root: Path, name: str) -> dict[str, object]:
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", name):
        raise ValueError("Environment name must use letters, numbers, underscores, or hyphens.")
    location = root / "scientific-environments" / name
    manifest_path = root / "environments" / f"{name}.json"
    if location.exists() or manifest_path.exists():
        raise FileExistsError(f"Environment already exists: {name}")
    location.parent.mkdir(parents=True, exist_ok=True)
    venv.EnvBuilder(with_pip=False, clear=False, symlinks=False).create(location)
    executable = location / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    try:
        completed = subprocess.run([str(executable), "--version"], capture_output=True, check=True, text=True)
        version = (completed.stdout or completed.stderr).strip()
    except (OSError, subprocess.SubprocessError) as error:
        shutil.rmtree(location)
        raise RuntimeError("FR-ENV-PYTHON-CREATE-FAILED") from error
    packages: dict[str, str] = {}
    fingerprint = hashlib.sha256(json.dumps(packages, sort_keys=True).encode()).hexdigest()
    manifest = EnvironmentManifest(name, "python", packages, path=str(location.resolve()), executable=str(executable.resolve()), python_version=version, package_fingerprint=fingerprint, created_at=datetime.now(timezone.utc).isoformat())
    try:
        save_manifest(root, manifest)
    except Exception:
        shutil.rmtree(location)
        raise
    return asdict(manifest)


def probe_environment(language: str) -> dict[str, object]:
    if language == "python":
        return {"language": "python", "available": True, "executable": sys.executable, "version": sys.version.split()[0]}
    executable = shutil.which("Rscript")
    return {"language": "r", "available": executable is not None, "executable": executable, "reason": None if executable else "FR-ENV-R-NOT-FOUND"}
