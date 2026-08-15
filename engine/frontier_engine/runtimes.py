"""Validated runtime-pack metadata and local capability probes."""

from __future__ import annotations

import json
import shutil
import subprocess
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
        listing = subprocess.run([executable, "list"], capture_output=True, text=True, timeout=5, check=True).stdout.splitlines()
    except (OSError, subprocess.SubprocessError) as error:
        return {"runtime": "ollama", "available": False, "reason": "FR-RUNTIME-OLLAMA-UNHEALTHY", "detail": str(error), "models": []}
    models = [line.split()[0] for line in listing[1:] if line.split()]
    return {"runtime": "ollama", "available": bool(models), "reason": None if models else "FR-RUNTIME-OLLAMA-NO-MODEL", "version": version, "models": models}
