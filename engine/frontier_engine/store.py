"""Durable local records for Frontier projects and scientific artifacts."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path


class ArchivedProjectError(ValueError):
    """Raised when a write would change an archived project."""


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


class FrontierStore:
    """SQLite metadata plus immutable, content-addressed artifact payloads."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.content_root = self.root / "content"
        self.content_root.mkdir(exist_ok=True)
        self.connection = sqlite3.connect(self.root / "frontier.sqlite3")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._migrate()

    def close(self) -> None:
        self.connection.close()

    def _migrate(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                instructions TEXT NOT NULL,
                archived_at TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(id),
                title TEXT NOT NULL,
                parent_session_id TEXT REFERENCES sessions(id),
                reasoning_effort TEXT NOT NULL,
                starred INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS artifacts (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(id),
                session_id TEXT REFERENCES sessions(id),
                name TEXT NOT NULL,
                media_type TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS artifact_versions (
                id TEXT PRIMARY KEY,
                artifact_id TEXT NOT NULL REFERENCES artifacts(id),
                version_number INTEGER NOT NULL,
                content_hash TEXT NOT NULL,
                content_path TEXT NOT NULL,
                messages_json TEXT NOT NULL,
                code_json TEXT NOT NULL,
                execution_log_json TEXT NOT NULL,
                environment_json TEXT NOT NULL,
                inputs_json TEXT NOT NULL,
                review_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(artifact_id, version_number)
            );
            """
        )
        self.connection.commit()

    def create_project(self, name: str, instructions: str = "") -> str:
        project_id = str(uuid.uuid4())
        self.connection.execute(
            "INSERT INTO projects(id, name, instructions, created_at) VALUES (?, ?, ?, ?)",
            (project_id, name, instructions, _utc_now()),
        )
        self.connection.commit()
        return project_id

    def archive_project(self, project_id: str) -> None:
        result = self.connection.execute(
            "UPDATE projects SET archived_at = ? WHERE id = ? AND archived_at IS NULL",
            (_utc_now(), project_id),
        )
        if result.rowcount != 1:
            raise KeyError(f"Active project not found: {project_id}")
        self.connection.commit()

    def create_session(
        self,
        project_id: str,
        title: str,
        reasoning_effort: str = "standard",
        parent_session_id: str | None = None,
    ) -> str:
        self._require_active_project(project_id)
        if parent_session_id is not None:
            parent = self.connection.execute(
                "SELECT project_id FROM sessions WHERE id = ?", (parent_session_id,)
            ).fetchone()
            if parent is None or parent["project_id"] != project_id:
                raise ValueError("A session can only fork within its own project.")
        session_id = str(uuid.uuid4())
        self.connection.execute(
            """INSERT INTO sessions(id, project_id, title, parent_session_id, reasoning_effort, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (session_id, project_id, title, parent_session_id, reasoning_effort, _utc_now()),
        )
        self.connection.commit()
        return session_id

    def set_session_starred(self, session_id: str, starred: bool) -> None:
        result = self.connection.execute(
            "UPDATE sessions SET starred = ? WHERE id = ?", (int(starred), session_id)
        )
        if result.rowcount != 1:
            raise KeyError(f"Session not found: {session_id}")
        self.connection.commit()

    def create_artifact(
        self, project_id: str, name: str, media_type: str, session_id: str | None = None
    ) -> str:
        self._require_active_project(project_id)
        if session_id is not None:
            session = self.connection.execute(
                "SELECT project_id FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if session is None or session["project_id"] != project_id:
                raise ValueError("An artifact session must belong to its project.")
        artifact_id = str(uuid.uuid4())
        self.connection.execute(
            """INSERT INTO artifacts(id, project_id, session_id, name, media_type, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (artifact_id, project_id, session_id, name, media_type, _utc_now()),
        )
        self.connection.commit()
        return artifact_id

    def add_artifact_version(
        self,
        artifact_id: str,
        content: bytes,
        *,
        messages: Mapping[str, object] | None = None,
        code: Mapping[str, object] | None = None,
        execution_log: Mapping[str, object] | None = None,
        environment: Mapping[str, object] | None = None,
        inputs: Mapping[str, object] | None = None,
        review: Mapping[str, object] | None = None,
    ) -> int:
        artifact = self.connection.execute(
            "SELECT project_id FROM artifacts WHERE id = ?", (artifact_id,)
        ).fetchone()
        if artifact is None:
            raise KeyError(f"Artifact not found: {artifact_id}")
        self._require_active_project(artifact["project_id"])
        content_hash = hashlib.sha256(content).hexdigest()
        content_path = self.content_root / content_hash[:2] / content_hash
        content_path.parent.mkdir(exist_ok=True)
        if not content_path.exists():
            content_path.write_bytes(content)
        version_number = self.connection.execute(
            "SELECT COALESCE(MAX(version_number), 0) + 1 FROM artifact_versions WHERE artifact_id = ?",
            (artifact_id,),
        ).fetchone()[0]
        self.connection.execute(
            """INSERT INTO artifact_versions(
                 id, artifact_id, version_number, content_hash, content_path, messages_json, code_json,
                 execution_log_json, environment_json, inputs_json, review_json, created_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()), artifact_id, version_number, content_hash, str(content_path.relative_to(self.root)),
                _json(messages), _json(code), _json(execution_log), _json(environment), _json(inputs), _json(review),
                _utc_now(),
            ),
        )
        self.connection.commit()
        return version_number

    def artifact_versions(self, artifact_id: str) -> list[dict[str, object]]:
        rows = self.connection.execute(
            "SELECT * FROM artifact_versions WHERE artifact_id = ? ORDER BY version_number", (artifact_id,)
        ).fetchall()
        return [
            {
                "version": row["version_number"],
                "content_hash": row["content_hash"],
                "content_path": row["content_path"],
                "messages": json.loads(row["messages_json"]),
                "code": json.loads(row["code_json"]),
                "execution_log": json.loads(row["execution_log_json"]),
                "environment": json.loads(row["environment_json"]),
                "inputs": json.loads(row["inputs_json"]),
                "review": json.loads(row["review_json"]),
            }
            for row in rows
        ]

    def _require_active_project(self, project_id: str) -> None:
        row = self.connection.execute(
            "SELECT archived_at FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"Project not found: {project_id}")
        if row["archived_at"] is not None:
            raise ArchivedProjectError(f"Project is archived: {project_id}")


def _json(value: Mapping[str, object] | None) -> str:
    return json.dumps(value or {}, sort_keys=True, separators=(",", ":"))
