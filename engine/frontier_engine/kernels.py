"""Persistent local scientific kernels with explicit lifecycle states."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import threading
import uuid
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class KernelResult:
    request_id: str
    state: str
    stdout: str
    stderr: str
    error: str | None = None


class PythonKernel:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._process: subprocess.Popen[str] | None = None

    @property
    def state(self) -> str:
        return "running" if self._process is not None and self._process.poll() is None else "stopped"

    def start(self) -> None:
        if self.state == "running": return
        self._process = subprocess.Popen([sys.executable, "-u", "-m", "frontier_engine.kernel_worker"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)

    def execute(self, code: str) -> KernelResult:
        with self._lock:
            self.start()
            if self._process is None or self._process.stdin is None or self._process.stdout is None: raise RuntimeError("FR-KERNEL-START: Python worker streams unavailable")
            request_id = str(uuid.uuid4())
            self._process.stdin.write(json.dumps({"id": request_id, "code": code}) + "\n"); self._process.stdin.flush()
            response = json.loads(self._process.stdout.readline())
            return KernelResult(response["id"], response["state"], response["stdout"], response["stderr"], response.get("error"))

    def interrupt(self) -> None:
        process = self._process
        if process is None:
            return
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None:
                stream.close()
        self._process = None

    def restart(self) -> None:
        self.interrupt(); self.start()

    def close(self) -> None: self.interrupt()


def probe_r() -> dict[str, Any]:
    executable = shutil.which("Rscript")
    return {"language": "R", "available": executable is not None, "reason": None if executable else "FR-KERNEL-R-NOT-FOUND", "executable": executable}
