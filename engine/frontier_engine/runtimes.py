"""Validated runtime-pack metadata and local capability probes."""

from __future__ import annotations

import json
import ipaddress
import os
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RuntimeManifest:
    identifier: str
    version: str
    protocol_version: int
    modalities: tuple[str, ...]
    operations: tuple[str, ...]
    formats: tuple[str, ...]
    health_command: tuple[str, ...]

    @classmethod
    def load(cls, path: Path) -> "RuntimeManifest":
        raw = json.loads(path.read_text(encoding="utf-8"))
        required = ("id", "version", "protocol_version", "modalities", "operations", "formats", "health_command")
        missing = [key for key in required if key not in raw]
        if missing:
            raise ValueError(f"FR-RUNTIME-MANIFEST: missing fields: {', '.join(missing)}")
        if not isinstance(raw["protocol_version"], int) or raw["protocol_version"] < 1:
            raise ValueError("FR-RUNTIME-MANIFEST: protocol_version must be a positive integer")
        return cls(raw["id"], raw["version"], raw["protocol_version"], tuple(raw["modalities"]), tuple(raw["operations"]), tuple(raw["formats"]), tuple(raw["health_command"]))

    def supports(self, modality: str, operation: str, model_format: str) -> bool:
        return modality in self.modalities and operation in self.operations and model_format in self.formats


def probe_ollama() -> dict[str, Any]:
    executable = shutil.which("ollama")
    if executable is None:
        return {"runtime": "ollama", "available": False, "reason": "FR-RUNTIME-OLLAMA-NOT-FOUND", "models": []}
    try:
        version = subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=5, check=True).stdout.strip()
        listing = _ollama_json("/api/tags").get("models", [])
        running = _ollama_json("/api/ps").get("models", [])
    except (OSError, subprocess.SubprocessError, urllib.error.URLError, ValueError, RuntimeError) as error:
        return {"runtime": "ollama", "available": False, "reason": "FR-RUNTIME-OLLAMA-UNHEALTHY", "detail": str(error), "models": []}
    installed = [{key: item.get(key) for key in ("name", "model", "size", "digest", "details")} for item in listing if isinstance(item, dict) and isinstance(item.get("model"), str)]
    loaded = [{key: item.get(key) for key in ("name", "model", "size", "size_vram", "context_length", "expires_at")} for item in running if isinstance(item, dict) and isinstance(item.get("model"), str)]
    models = [str(item["model"]) for item in installed]
    return {"runtime": "ollama", "available": bool(models), "reason": None if models else "FR-RUNTIME-OLLAMA-NO-MODEL", "version": version, "endpoint": _ollama_endpoint(), "models": models, "installed_models": installed, "loaded_models": loaded}


def probe_lm_studio_library() -> dict[str, Any]:
    settings_path = Path.home() / ".lmstudio" / "settings.json"
    models_root = Path.home() / ".lmstudio" / "models"
    if settings_path.is_file():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            configured = settings.get("downloadsFolder") if isinstance(settings, dict) else None
            if isinstance(configured, str) and configured.strip():
                models_root = Path(configured).expanduser()
        except (OSError, json.JSONDecodeError):
            pass
    if not models_root.is_dir():
        return {"source": "lmstudio-library", "available": False, "reason": "FR-LM-STUDIO-LIBRARY-NOT-FOUND", "models_root": str(models_root), "models": []}
    models = [
        {
            "key": str(path.relative_to(models_root)).replace("\\", "/"),
            "display_name": path.stem,
            "path": str(path.resolve()),
            "size_bytes": path.stat().st_size,
            "format": "gguf",
            "execution_runtime": "shoko-managed-gguf",
        }
        for path in sorted(models_root.rglob("*.gguf"))
        if path.is_file() and not path.name.lower().startswith("mmproj-")
    ]
    return {"source": "lmstudio-library", "available": bool(models), "reason": None if models else "FR-LM-STUDIO-LIBRARY-NO-COMPATIBLE-MODEL", "models_root": str(models_root.resolve()), "models": models}


class LocalRuntimeUnavailable(RuntimeError):
    pass


class OllamaStream(Iterator[str]):
    def __init__(self, model: str, prompt: str, options: Mapping[str, object] | None = None, keep_alive: str = "15m") -> None:
        self.model = model
        self.prompt = prompt
        self.options = dict(options or {})
        self.keep_alive = keep_alive
        self.metrics: dict[str, object] = {}
        self._iterator = self._read()

    def __iter__(self) -> "OllamaStream":
        return self

    def __next__(self) -> str:
        return next(self._iterator)

    def _read(self) -> Iterator[str]:
        request = _ollama_request("/api/generate", {"model": self.model, "prompt": self.prompt, "stream": True, "keep_alive": self.keep_alive, "options": self.options})
        try:
            with _ollama_open(request, timeout=300) as response:
                for raw_line in response:
                    if not raw_line.strip():
                        continue
                    payload = json.loads(raw_line)
                    if payload.get("error"):
                        raise RuntimeError(f"FR-RUNTIME-OLLAMA-API: {payload['error']}")
                    if payload.get("done"):
                        self.metrics = _ollama_metrics(payload)
                    text = payload.get("response", "")
                    if text:
                        yield str(text)
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as error:
            raise RuntimeError(f"FR-RUNTIME-OLLAMA-GENERATION-FAILED: {error}") from error


def stream_ollama(model: str, prompt: str, options: Mapping[str, object] | None = None, keep_alive: str = "15m", runtime_probe: dict[str, Any] | None = None) -> Iterator[str]:
    """Yield output from the local process only after its runtime probe succeeds."""
    probe = runtime_probe or probe_ollama()
    if not probe["available"]:
        raise LocalRuntimeUnavailable(str(probe["reason"]))
    if model not in probe["models"]:
        raise LocalRuntimeUnavailable("FR-RUNTIME-OLLAMA-MODEL-NOT-INSTALLED")
    return OllamaStream(model, prompt, options, keep_alive)


def warmup_ollama(model: str, options: Mapping[str, object], keep_alive: str, runtime_probe: dict[str, Any] | None = None) -> dict[str, object]:
    probe = runtime_probe or probe_ollama()
    if not probe["available"] or model not in probe["models"]:
        raise LocalRuntimeUnavailable(str(probe.get("reason") or "FR-RUNTIME-OLLAMA-MODEL-NOT-INSTALLED"))
    result = _ollama_json("/api/generate", {"model": model, "prompt": "", "stream": False, "keep_alive": keep_alive, "options": dict(options)}, timeout=300)
    loaded = _ollama_json("/api/ps").get("models", [])
    exact = next((item for item in loaded if isinstance(item, dict) and item.get("model") == model), None)
    if exact is None:
        raise RuntimeError("FR-RUNTIME-OLLAMA-WARMUP-VERIFY")
    return {"model": model, "keep_alive": keep_alive, "options": dict(options), "metrics": _ollama_metrics(result), "loaded": exact}


class OllamaEmbedder:
    """Explicit local Ollama embedding adapter for hybrid retrieval."""

    def __init__(self, model: str, runtime_probe: dict[str, Any] | None = None) -> None:
        probe = runtime_probe or probe_ollama()
        if not probe["available"] or model not in probe["models"]:
            raise LocalRuntimeUnavailable(str(probe.get("reason") or "FR-RUNTIME-OLLAMA-MODEL-NOT-INSTALLED"))
        self.model = model

    def embed(self, text: str) -> list[float]:
        result = _ollama_json("/api/embed", {"model": self.model, "input": text}, timeout=60)
        embeddings = result.get("embeddings")
        if not isinstance(embeddings, list) or len(embeddings) != 1 or not isinstance(embeddings[0], list) or not embeddings[0] or not all(isinstance(value, (int, float)) for value in embeddings[0]):
            raise RuntimeError("FR-RUNTIME-OLLAMA-EMBEDDING-INVALID")
        return [float(value) for value in embeddings[0]]


def transcribe_whisper_cpp(executable: str, model_path: Path, audio_path: Path, timeout_seconds: int = 600) -> dict[str, object]:
    """Run an explicitly selected local whisper.cpp CLI and verify its text output."""
    if not executable.strip():
        raise ValueError("FR-AUDIO-WHISPER-EXECUTABLE")
    if not 1 <= timeout_seconds <= 3600:
        raise ValueError("FR-AUDIO-WHISPER-TIMEOUT")
    model = model_path.expanduser().resolve()
    audio = audio_path.expanduser().resolve()
    if not model.is_file():
        raise FileNotFoundError("FR-AUDIO-WHISPER-MODEL-NOT-FOUND")
    if not audio.is_file():
        raise FileNotFoundError("FR-AUDIO-WHISPER-AUDIO-NOT-FOUND")
    if audio.suffix.lower() not in {".flac", ".mp3", ".ogg", ".wav"}:
        raise ValueError("FR-AUDIO-WHISPER-AUDIO-FORMAT")
    candidate = Path(executable).expanduser()
    resolved_executable = candidate.resolve() if candidate.is_file() else shutil.which(executable)
    if not resolved_executable:
        raise LocalRuntimeUnavailable("FR-AUDIO-WHISPER-NOT-FOUND")
    runtime = str(resolved_executable)
    try:
        subprocess.run([runtime, "--help"], capture_output=True, text=True, timeout=10, check=True)
        with tempfile.TemporaryDirectory(prefix="shokos-llm-whisper-") as directory:
            output_base = Path(directory) / "transcript"
            subprocess.run([runtime, "--model", str(model), "--file", str(audio), "--output-txt", "--output-file", str(output_base), "--no-prints"], capture_output=True, text=True, timeout=timeout_seconds, check=True)
            output = output_base.with_suffix(".txt")
            if not output.is_file():
                raise RuntimeError("FR-AUDIO-WHISPER-OUTPUT-MISSING")
            transcript = output.read_text(encoding="utf-8").strip()
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("FR-AUDIO-WHISPER-TIMEOUT") from error
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or "").strip()[:600]
        raise RuntimeError(f"FR-AUDIO-WHISPER-FAILED: {detail or error.returncode}") from error
    if not transcript:
        raise RuntimeError("FR-AUDIO-WHISPER-EMPTY-OUTPUT")
    return {"runtime": runtime, "model_path": str(model), "audio_path": str(audio), "transcript": transcript, "output_bytes": len(transcript.encode("utf-8"))}


def stream_ollama_pull(model: str) -> Iterator[str]:
    """Yield local Ollama pull output without selecting a fallback model."""
    model = model.strip()
    if not model:
        raise ValueError("An Ollama model identifier is required.")
    executable = shutil.which("ollama")
    if executable is None:
        raise LocalRuntimeUnavailable("FR-RUNTIME-OLLAMA-NOT-FOUND")
    try:
        subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=5, check=True)
    except (OSError, subprocess.SubprocessError) as error:
        raise LocalRuntimeUnavailable("FR-RUNTIME-OLLAMA-UNHEALTHY") from error
    process = subprocess.Popen([executable, "pull", model], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        if process.stdout is None:
            raise RuntimeError("FR-RUNTIME-OLLAMA-PULL-STREAM-MISSING")
        yield from process.stdout
        if process.wait() != 0:
            raise RuntimeError("FR-RUNTIME-OLLAMA-PULL-FAILED")
    finally:
        if process.poll() is None:
            process.terminate()


def _ollama_endpoint() -> str:
    raw = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").strip()
    if "://" not in raw:
        raw = f"http://{raw}"
    parsed = urllib.parse.urlparse(raw)
    host = parsed.hostname
    if parsed.scheme not in {"http", "https"} or host is None:
        raise ValueError("FR-RUNTIME-OLLAMA-ENDPOINT")
    try:
        local = ipaddress.ip_address(host).is_loopback
    except ValueError:
        local = host.lower() == "localhost"
    if not local:
        raise ValueError("FR-RUNTIME-OLLAMA-NONLOCAL-ENDPOINT")
    return raw.rstrip("/")


def _ollama_request(path: str, payload: Mapping[str, object] | None = None) -> urllib.request.Request:
    body = json.dumps(payload).encode() if payload is not None else None
    return urllib.request.Request(f"{_ollama_endpoint()}{path}", data=body, headers={"Content-Type": "application/json"} if body is not None else {}, method="POST" if body is not None else "GET")


def _ollama_open(request: urllib.request.Request, timeout: float):
    return urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=timeout)


def _ollama_json(path: str, payload: Mapping[str, object] | None = None, timeout: float = 5) -> dict[str, Any]:
    with _ollama_open(_ollama_request(path, payload), timeout) as response:
        result = json.load(response)
    if not isinstance(result, dict):
        raise ValueError("FR-RUNTIME-OLLAMA-INVALID-RESPONSE")
    if result.get("error"):
        raise RuntimeError(f"FR-RUNTIME-OLLAMA-API: {result['error']}")
    return result


def _ollama_metrics(payload: Mapping[str, object]) -> dict[str, object]:
    metrics = {key: payload.get(key) for key in ("done_reason", "total_duration", "load_duration", "prompt_eval_count", "prompt_eval_duration", "eval_count", "eval_duration") if payload.get(key) is not None}
    eval_count = int(payload.get("eval_count") or 0)
    eval_duration = int(payload.get("eval_duration") or 0)
    if eval_count and eval_duration:
        metrics["tokens_per_second"] = round(eval_count / (eval_duration / 1_000_000_000), 2)
    return metrics
