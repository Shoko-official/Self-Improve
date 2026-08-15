"""Typed project-workspace tools constrained by exact folder grants."""

from __future__ import annotations

import json
from pathlib import Path

from .agent_state import AgentStateStore
from .store import FrontierStore


class WorkspaceToolDenied(PermissionError):
    pass


class ProjectWorkspaceTools:
    def __init__(self, store: FrontierStore, agent_state: AgentStateStore, project_id: str, workspace: Path) -> None:
        self.store = store
        self.agent_state = agent_state
        self.project_id = project_id
        self.workspace = workspace.resolve(strict=True)

    def list_files(self) -> tuple[str, ...]:
        self._authorize(self.workspace, "read")
        result = tuple(str(path.relative_to(self.workspace)) for path in sorted(self.workspace.rglob("*")) if path.is_file())
        self._record("workspace.list", {}, "succeeded", {"files": result})
        return result

    def read_file(self, relative_path: str) -> str:
        path = self._resolve(relative_path)
        try:
            self._authorize(path, "read")
            content = path.read_text(encoding="utf-8")
        except Exception as error:
            self._record("workspace.read", {"path": relative_path}, "failed", {"error": str(error)})
            raise
        self._record("workspace.read", {"path": relative_path}, "succeeded", {"bytes": len(content.encode())})
        return content

    def write_file(self, relative_path: str, content: str) -> Path:
        path = self._resolve(relative_path)
        try:
            self._authorize(path, "write")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        except Exception as error:
            self._record("workspace.write", {"path": relative_path}, "failed", {"error": str(error)})
            raise
        self._record("workspace.write", {"path": relative_path}, "succeeded", {"bytes": len(content.encode())})
        return path

    def _resolve(self, relative_path: str) -> Path:
        path = Path(relative_path)
        if not relative_path or path.is_absolute() or ".." in path.parts:
            raise ValueError("FR-WORKSPACE-PATH: a relative non-traversing path is required")
        candidate = (self.workspace / path).resolve(strict=False)
        try:
            candidate.relative_to(self.workspace)
        except ValueError as error:
            raise ValueError("FR-WORKSPACE-PATH: path escapes workspace") from error
        return candidate

    def _authorize(self, path: Path, operation: str) -> None:
        if not self.store.authorize_project_path(self.project_id, path, operation):
            raise WorkspaceToolDenied(f"FR-WORKSPACE-PERMISSION: project {operation} grant required")

    def _record(self, tool_name: str, request: dict[str, object], state: str, result: dict[str, object]) -> None:
        self.agent_state.record_tool_call(self.project_id, tool_name, json.dumps(request, sort_keys=True), state, json.dumps(result, sort_keys=True))
