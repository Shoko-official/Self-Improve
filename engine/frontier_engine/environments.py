"""Named scientific environment manifests and truthful local probes."""

from __future__ import annotations

import json
import hashlib
import os
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
    runtime_version: str | None = None
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


def install_python_packages(root: Path, name: str, packages: list[str]) -> dict[str, object]:
    if not packages or any(not package.strip() or package.lstrip().startswith("-") for package in packages):
        raise ValueError("At least one package spec without installer flags is required.")
    manifest_path = root / "environments" / f"{name}.json"
    if not manifest_path.exists(): raise FileNotFoundError(f"Environment manifest not found: {name}")
    manifest = EnvironmentManifest(**json.loads(manifest_path.read_text(encoding="utf-8")))
    if manifest.language != "python" or not manifest.executable: raise ValueError("Only Python environments with an executable can install packages.")
    executable = Path(manifest.executable)
    try:
        pip = subprocess.run([str(executable), "-m", "pip", "--version"], capture_output=True, text=True)
        if pip.returncode != 0:
            bootstrap = subprocess.run([str(executable), "-m", "ensurepip", "--upgrade"], capture_output=True, text=True)
            if bootstrap.returncode != 0: raise RuntimeError("FR-ENV-PIP-BOOTSTRAP-FAILED")
        installed = subprocess.run([str(executable), "-m", "pip", "install", "--disable-pip-version-check", "--no-input", *packages], capture_output=True, text=True)
        if installed.returncode != 0: raise RuntimeError("FR-ENV-PIP-INSTALL-FAILED")
        listing = subprocess.run([str(executable), "-m", "pip", "list", "--format=json"], capture_output=True, text=True)
        if listing.returncode != 0: raise RuntimeError("FR-ENV-PIP-LIST-FAILED")
        records = json.loads(listing.stdout or "[]")
        package_map = {str(record["name"]): str(record["version"]) for record in records}
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError, KeyError) as error:
        raise RuntimeError("FR-ENV-PIP-INSTALL-FAILED") from error
    updated = EnvironmentManifest(**{**asdict(manifest), "packages": package_map, "package_fingerprint": hashlib.sha256(json.dumps(package_map, sort_keys=True).encode()).hexdigest()})
    manifest_path.write_text(json.dumps(asdict(updated), sort_keys=True), encoding="utf-8")
    return asdict(updated)


def create_r_environment(root: Path, name: str) -> dict[str, object]:
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", name): raise ValueError("Environment name must use letters, numbers, underscores, or hyphens.")
    executable = shutil.which("Rscript")
    if executable is None: raise RuntimeError("FR-ENV-R-NOT-FOUND")
    manifest_path = root / "environments" / f"{name}.json"
    if manifest_path.exists(): raise FileExistsError(f"Environment already exists: {name}")
    library = root / "scientific-environments" / name / "r-library"
    library.mkdir(parents=True, exist_ok=True)
    try:
        probe = subprocess.run([executable, "--vanilla", "-e", "cat(R.version.string)"], capture_output=True, text=True)
        if probe.returncode != 0: raise RuntimeError("FR-ENV-R-CREATE-FAILED")
    except (OSError, subprocess.SubprocessError) as error:
        shutil.rmtree(library.parent, ignore_errors=True)
        raise RuntimeError("FR-ENV-R-CREATE-FAILED") from error
    packages: dict[str, str] = {}
    manifest = EnvironmentManifest(name, "r", packages, path=str(library.resolve()), executable=str(Path(executable).resolve()), runtime_version=probe.stdout.strip(), package_fingerprint=hashlib.sha256(json.dumps(packages, sort_keys=True).encode()).hexdigest(), created_at=datetime.now(timezone.utc).isoformat())
    try: save_manifest(root, manifest)
    except Exception:
        shutil.rmtree(library.parent, ignore_errors=True)
        raise
    return asdict(manifest)


def install_r_packages(root: Path, name: str, packages: list[str], repository: str = "https://cloud.r-project.org") -> dict[str, object]:
    if not packages or any(not re.fullmatch(r"[A-Za-z][A-Za-z0-9._-]*", package) for package in packages): raise ValueError("R package names must be simple package identifiers.")
    if not repository.startswith("https://"): raise ValueError("R package repositories must use HTTPS.")
    manifest_path = root / "environments" / f"{name}.json"
    if not manifest_path.exists(): raise FileNotFoundError(f"Environment manifest not found: {name}")
    manifest = EnvironmentManifest(**json.loads(manifest_path.read_text(encoding="utf-8")))
    if manifest.language != "r" or not manifest.executable or not manifest.path: raise ValueError("Only R environments with a library can install packages.")
    package_vector = ",".join(json.dumps(package) for package in packages)
    expression = f"install.packages(c({package_vector}), repos={json.dumps(repository)}); x <- installed.packages(lib.loc={json.dumps(manifest.path)})[,c('Package','Version'),drop=FALSE]; write.table(x, sep='\\t', row.names=FALSE, quote=FALSE)"
    env = os.environ.copy(); env["R_LIBS_USER"] = manifest.path
    try:
        installed = subprocess.run([manifest.executable, "--vanilla", "-e", expression], capture_output=True, text=True, env=env)
        if installed.returncode != 0: raise RuntimeError("FR-ENV-R-INSTALL-FAILED")
        rows = [line.split("\t", 1) for line in installed.stdout.splitlines() if "\t" in line]
        package_map = {name_value: version for name_value, version in rows if name_value != "Package"}
    except (OSError, subprocess.SubprocessError) as error:
        raise RuntimeError("FR-ENV-R-INSTALL-FAILED") from error
    updated = EnvironmentManifest(**{**asdict(manifest), "packages": package_map, "package_fingerprint": hashlib.sha256(json.dumps(package_map, sort_keys=True).encode()).hexdigest()})
    manifest_path.write_text(json.dumps(asdict(updated), sort_keys=True), encoding="utf-8")
    return asdict(updated)


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
