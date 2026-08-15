"""Permission-gated local shell execution with durable job records."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path

from .store import FrontierStore


class ShellPermissionDenied(PermissionError):
    pass


def execute_project_shell(store: FrontierStore, project_id: str, working_directory: Path, command: Sequence[str], timeout_seconds: float = 30) -> dict[str, object]:
    if not command or any(not value for value in command):
        raise ValueError("FR-SHELL-COMMAND: an exact command is required")
    if timeout_seconds <= 0:
        raise ValueError("FR-SHELL-TIMEOUT: timeout must be positive")
    working_directory = working_directory.resolve(strict=True)
    if not working_directory.is_dir():
        raise ValueError("FR-SHELL-WORKDIR: working directory is required")
    if not store.authorize_project_path(project_id, working_directory, "write"):
        raise ShellPermissionDenied("FR-SHELL-PERMISSION: project write grant required for working directory")
    job_id = store.create_job(project_id, "shell.execute", {"command": list(command), "working_directory": str(working_directory), "timeout_seconds": timeout_seconds})
    store.claim_job(job_id)
    try:
        completed = subprocess.run(command, cwd=working_directory, capture_output=True, text=True, timeout=timeout_seconds, check=False)
    except subprocess.TimeoutExpired as error:
        return store.fail_job(job_id, {"code": "FR-SHELL-TIMEOUT", "evidence": str(error)})
    result = {"exit_code": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}
    if completed.returncode == 0:
        return store.complete_job(job_id, result)
    return store.fail_job(job_id, {"code": "FR-SHELL-EXIT", "exit_code": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr})
