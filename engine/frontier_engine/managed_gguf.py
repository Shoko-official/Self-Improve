"""Pinned, self-managed llama.cpp runtime for local GGUF inference."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import socket
import subprocess
import tarfile
import tempfile
import time
import urllib.request
import zipfile
from collections.abc import Iterator
from pathlib import Path


RUNTIME_VERSION = "b10517"
ASSETS = {
    "windows-x86_64": ("llama-b10517-bin-win-cpu-x64.zip", "f3fed0673c934ade45663a8e29220a0903b58ad7eff91eeeef606a37061cd031", 18_507_219),
    "macos-aarch64": ("llama-b10517-bin-macos-arm64.tar.gz", "d5d9ed544126f9f1af62252223f70ba11a75d1ee6f63bb61999e398bb8c74ffc", 11_090_071),
    "macos-x86_64": ("llama-b10517-bin-macos-x64.tar.gz", "f0aa2c8b9b9b2a5b44c767b83e3f47c4e7e1da9473a038f11e6d1e6a983d4b2b", 11_396_043),
    "linux-aarch64": ("llama-b10517-bin-ubuntu-arm64.tar.gz", "0005598eb1bbd6206e9089ec618c7d256d7c9756495cc8a95045ee7e2e4592e5", 13_529_444),
    "linux-x86_64": ("llama-b10517-bin-ubuntu-x64.tar.gz", "dfe6304a96af76975838db974eacfb825a5bcc71096c8553e06a63ff2c0240b1", 16_667_382),
}


def probe_managed_gguf(root: Path) -> dict[str, object]:
    runtime_root = root / "runtimes" / "shoko-gguf" / RUNTIME_VERSION
    executable = _find_executable(runtime_root)
    launch = _probe_executable(executable) if executable is not None else None
    available = executable is not None and launch is not None and launch[0]
    return {
        "runtime": "shoko-gguf",
        "available": available,
        "version": RUNTIME_VERSION,
        "path": str(executable) if executable is not None else None,
        "reason": None if available else launch[1] if launch is not None else "FR-SHOKO-GGUF-RUNTIME-NOT-INSTALLED",
        "exit_code": launch[2] if launch is not None else None,
        "independent_of_lm_studio": True,
    }


def install_managed_gguf(root: Path) -> dict[str, object]:
    platform_key = _platform_key()
    if platform_key not in ASSETS:
        raise RuntimeError("FR-SHOKO-GGUF-PLATFORM-UNSUPPORTED")
    filename, expected_sha256, expected_bytes = ASSETS[platform_key]
    destination = root / "runtimes" / "shoko-gguf" / RUNTIME_VERSION
    existing = _find_executable(destination)
    if existing is not None:
        result = probe_managed_gguf(root)
        return {**result, "installed": False, "reused": bool(result["available"])}
    destination.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://github.com/ggml-org/llama.cpp/releases/download/{RUNTIME_VERSION}/{filename}"
    with tempfile.TemporaryDirectory(dir=destination.parent, prefix="install-") as directory:
        temporary = Path(directory)
        archive = temporary / filename
        _download(url, archive, expected_bytes)
        digest = _sha256(archive)
        if digest != expected_sha256:
            raise RuntimeError("FR-SHOKO-GGUF-RUNTIME-HASH-MISMATCH")
        extracted = temporary / "extracted"
        extracted.mkdir()
        _extract(archive, extracted)
        executable = _find_executable(extracted)
        if executable is None:
            raise RuntimeError("FR-SHOKO-GGUF-RUNTIME-EXECUTABLE-MISSING")
        receipt = {"version": RUNTIME_VERSION, "asset": filename, "sha256": digest, "source": url, "license": "MIT"}
        (extracted / "shoko-runtime-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
        if os.name != "nt":
            executable.chmod(executable.stat().st_mode | 0o111)
        os.replace(extracted, destination)
    return {**probe_managed_gguf(root), "installed": True, "reused": False}


def stream_managed_gguf(root: Path, model: Path, prompt: str, max_tokens: int = 512) -> Iterator[str]:
    executable = _find_server(root / "runtimes" / "shoko-gguf" / RUNTIME_VERSION)
    model = model.resolve(strict=True)
    if executable is None:
        raise RuntimeError("FR-SHOKO-GGUF-SERVER-NOT-INSTALLED")
    if model.suffix.lower() != ".gguf":
        raise ValueError("FR-SHOKO-GGUF-MODEL-FORMAT")
    port = _available_loopback_port()
    command = [*_server_command(executable), "--model", str(model), "--host", "127.0.0.1", "--port", str(port), "--no-webui", "--log-disable", "--reasoning", "off"]
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    try:
        _wait_for_server(process, port)
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/v1/chat/completions",
            data=json.dumps({"messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens, "stream": False}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=180) as response:
            payload = json.loads(response.read().decode("utf-8"))
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("FR-SHOKO-GGUF-RESPONSE-MALFORMED")
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str):
            raise RuntimeError("FR-SHOKO-GGUF-RESPONSE-MALFORMED")
        yield content
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


def _available_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _wait_for_server(process: subprocess.Popen[str], port: int) -> None:
    deadline = time.monotonic() + 120
    health_url = f"http://127.0.0.1:{port}/health"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stderr = process.stderr.read() if process.stderr is not None else ""
            detail = stderr.strip() or f"process exit {process.returncode}"
            raise RuntimeError(f"FR-SHOKO-GGUF-SERVER-FAILED: {detail}")
        try:
            with urllib.request.urlopen(health_url, timeout=1) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.2)
    raise RuntimeError("FR-SHOKO-GGUF-SERVER-STARTUP-TIMEOUT")


def _platform_key() -> str:
    system = platform.system().lower()
    system = "macos" if system == "darwin" else system
    machine = platform.machine().lower()
    machine = "x86_64" if machine in {"amd64", "x64"} else "aarch64" if machine in {"arm64", "aarch64"} else machine
    return f"{system}-{machine}"


def _find_executable(root: Path) -> Path | None:
    if not root.is_dir():
        return None
    names = ("shoko-llama.exe", "llama-cli.exe") if os.name == "nt" else ("shoko-llama", "llama-cli")
    for name in names:
        match = next((path for path in root.rglob(name) if path.is_file()), None)
        if match is not None:
            return match
    return None


def _find_server(root: Path) -> Path | None:
    if not root.is_dir():
        return None
    names = ("shoko-llama.exe", "llama-server.exe") if os.name == "nt" else ("shoko-llama", "llama-server")
    for name in names:
        match = next((path for path in root.rglob(name) if path.is_file()), None)
        if match is not None:
            return match
    return None


def _runtime_command(executable: Path) -> list[str]:
    return [str(executable), "cli"] if executable.stem == "shoko-llama" else [str(executable)]


def _server_command(executable: Path) -> list[str]:
    return [str(executable), "serve"] if executable.stem == "shoko-llama" else [str(executable)]


def _probe_executable(executable: Path) -> tuple[bool, str | None, int | None]:
    try:
        result = subprocess.run([*_runtime_command(executable), "--help"], capture_output=True, timeout=8)
    except (OSError, subprocess.TimeoutExpired):
        return False, "FR-SHOKO-GGUF-RUNTIME-LAUNCH-FAILED", None
    if result.returncode == 0:
        return True, None, 0
    if result.returncode == -1058471934:
        return False, "FR-SHOKO-GGUF-RUNTIME-WINDOWS-INTEGRITY-BLOCKED", result.returncode
    return False, "FR-SHOKO-GGUF-RUNTIME-LAUNCH-FAILED", result.returncode


def _download(url: str, destination: Path, expected_bytes: int) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "Shokos-LLM/0.1"})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=60) as response, destination.open("wb") as output:
        shutil.copyfileobj(response, output, 1024 * 1024)
    if destination.stat().st_size != expected_bytes:
        raise RuntimeError("FR-SHOKO-GGUF-RUNTIME-SIZE-MISMATCH")


def _extract(archive: Path, destination: Path) -> None:
    if archive.suffix.lower() == ".zip":
        with zipfile.ZipFile(archive) as source:
            _safe_members(destination, [item.filename for item in source.infolist()])
            source.extractall(destination)
    else:
        with tarfile.open(archive, "r:gz") as source:
            _safe_members(destination, [item.name for item in source.getmembers()])
            source.extractall(destination, filter="data")


def _safe_members(destination: Path, names: list[str]) -> None:
    base = destination.resolve()
    for name in names:
        target = (destination / name).resolve()
        try:
            target.relative_to(base)
        except ValueError as error:
            raise RuntimeError("FR-SHOKO-GGUF-RUNTIME-UNSAFE-ARCHIVE") from error


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
