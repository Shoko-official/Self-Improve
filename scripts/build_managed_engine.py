"""Build one native Frontier engine sidecar and its verification manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import venv
from pathlib import Path


def target_identity(target_triple: str) -> tuple[str, str, str]:
    triple = target_triple.lower()
    if "windows" in triple:
        system, suffix = "windows", ".exe"
    elif "darwin" in triple or "apple" in triple:
        system, suffix = "macos", ""
    elif "linux" in triple:
        system, suffix = "linux", ""
    else:
        raise ValueError(f"FR-BUNDLE-TARGET-UNSUPPORTED: {target_triple}")
    if triple.startswith(("x86_64", "amd64")):
        architecture = "x86_64"
    elif triple.startswith(("aarch64", "arm64")):
        architecture = "aarch64"
    else:
        raise ValueError(f"FR-BUNDLE-ARCH-UNSUPPORTED: {target_triple}")
    return system, architecture, suffix


def host_target_triple() -> str:
    output = subprocess.run(["rustc", "-vV"], capture_output=True, text=True, check=True).stdout
    for line in output.splitlines():
        if line.startswith("host: "):
            return line.removeprefix("host: ").strip()
    raise RuntimeError("FR-BUNDLE-TARGET-MISSING: rustc did not report a host triple")


def write_manifest(path: Path, executable: Path, target_triple: str) -> dict[str, object]:
    system, architecture, suffix = target_identity(target_triple)
    expected_name = f"frontier-engine{suffix}"
    digest = hashlib.sha256(executable.read_bytes()).hexdigest()
    manifest = {
        "id": "frontier-engine",
        "version": "0.1.0",
        "protocol_version": 1,
        "target_triple": target_triple,
        "target_platform": system,
        "target_architecture": architecture,
        "executable": expected_name,
        "sha256": digest,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def isolated_build_python(root: Path) -> Path:
    environment = root / "target" / "managed-engine-venv"
    python = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    if not python.is_file():
        venv.EnvBuilder(with_pip=True, clear=True).create(environment)
    requirements = root / "requirements-build.txt"
    required_hash = hashlib.sha256(requirements.read_bytes()).hexdigest()
    stamp = environment / ".requirements.sha256"
    if not stamp.is_file() or stamp.read_text(encoding="utf-8").strip() != required_hash:
        subprocess.run(
            [str(python), "-m", "pip", "install", "--disable-pip-version-check", "--upgrade", "-r", str(requirements)],
            check=True,
        )
        subprocess.run([str(python), "-m", "pip", "check"], check=True)
        stamp.write_text(required_hash + "\n", encoding="utf-8")
    return python


def copy_runtime_licenses(root: Path, build_python: Path) -> list[str]:
    destination = root / "runtime-packs" / "managed-engine" / "licenses"
    destination.mkdir(parents=True, exist_ok=True)
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if not python_license.is_file():
        raise RuntimeError("FR-BUNDLE-PYTHON-LICENSE-MISSING")
    shutil.copyfile(python_license, destination / "PYTHON-LICENSE.txt")
    finder = "import importlib.metadata as m; d=m.distribution('pyinstaller'); print(next(str(d.locate_file(f)) for f in d.files if str(f).replace('\\\\','/').endswith('licenses/COPYING.txt')))"
    pyinstaller_license = Path(subprocess.run([str(build_python), "-c", finder], capture_output=True, text=True, check=True).stdout.strip())
    if not pyinstaller_license.is_file():
        raise RuntimeError("FR-BUNDLE-PYINSTALLER-LICENSE-MISSING")
    shutil.copyfile(pyinstaller_license, destination / "PYINSTALLER-COPYING.txt")
    return [str(destination / "PYTHON-LICENSE.txt"), str(destination / "PYINSTALLER-COPYING.txt")]


def build(root: Path, target_triple: str) -> dict[str, object]:
    system, _, suffix = target_identity(target_triple)
    if target_identity(host_target_triple())[:2] != target_identity(target_triple)[:2]:
        raise ValueError("FR-BUNDLE-CROSS-COMPILE-UNSUPPORTED: build the sidecar on its target host")
    binary_name = f"frontier-engine-{target_triple}"
    binaries = root / "src-tauri" / "binaries"
    work = root / "target" / "managed-engine"
    shutil.rmtree(work, ignore_errors=True)
    binaries.mkdir(parents=True, exist_ok=True)
    build_python = isolated_build_python(root)
    command = [
        str(build_python),
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        "--onefile",
        "--name",
        binary_name,
        "--distpath",
        str(binaries),
        "--workpath",
        str(work / "work"),
        "--specpath",
        str(work / "spec"),
        "--paths",
        str(root / "engine"),
        str(root / "scripts" / "managed_engine_entry.py"),
    ]
    subprocess.run(command, cwd=root, check=True)
    executable = binaries / f"{binary_name}{suffix}"
    if not executable.is_file():
        raise RuntimeError("FR-BUNDLE-OUTPUT-MISSING: PyInstaller did not produce the sidecar")
    manifest_path = root / "runtime-packs" / "managed-engine" / "manifest.json"
    manifest = write_manifest(manifest_path, executable, target_triple)
    licenses = copy_runtime_licenses(root, build_python)
    return {"binary": str(executable), "manifest": str(manifest_path), "licenses": licenses, "sha256": manifest["sha256"], "platform": system}


def main() -> int:
    parser = argparse.ArgumentParser(prog="build-managed-engine")
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--target-triple")
    args = parser.parse_args()
    result = build(args.root.resolve(), args.target_triple or host_target_triple())
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
