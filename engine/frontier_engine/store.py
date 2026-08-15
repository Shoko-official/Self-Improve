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


_REASONING_EFFORTS = {"compact", "standard", "extended"}


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
            CREATE TABLE IF NOT EXISTS project_folder_grants (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(id),
                path TEXT NOT NULL,
                operation TEXT NOT NULL CHECK(operation IN ('read', 'write')),
                created_at TEXT NOT NULL,
                revoked_at TEXT,
                UNIQUE(project_id, path, operation)
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
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(id),
                session_id TEXT REFERENCES sessions(id),
                parent_job_id TEXT REFERENCES jobs(id),
                operation TEXT NOT NULL,
                state TEXT NOT NULL CHECK(state IN ('queued', 'running', 'cancel_requested', 'cancelled', 'succeeded', 'failed')),
                request_json TEXT NOT NULL,
                result_json TEXT,
                diagnostic_json TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT
            );
            CREATE TABLE IF NOT EXISTS job_events (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL REFERENCES jobs(id),
                sequence_number INTEGER NOT NULL,
                kind TEXT NOT NULL,
                detail_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(job_id, sequence_number)
            );
            CREATE INDEX IF NOT EXISTS job_events_by_job ON job_events(job_id, sequence_number);
            CREATE TABLE IF NOT EXISTS generations (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL UNIQUE REFERENCES jobs(id),
                runtime TEXT NOT NULL,
                model TEXT NOT NULL,
                prompt TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS generation_chunks (
                generation_id TEXT NOT NULL REFERENCES generations(id),
                sequence_number INTEGER NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY(generation_id, sequence_number)
            );
            """
        )
        columns = {row["name"] for row in self.connection.execute("PRAGMA table_info(jobs)")}
        if "parent_job_id" not in columns:
            self.connection.execute("ALTER TABLE jobs ADD COLUMN parent_job_id TEXT REFERENCES jobs(id)")
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

    def set_project_instructions(self, project_id: str, instructions: str) -> None:
        result = self.connection.execute(
            "UPDATE projects SET instructions = ? WHERE id = ? AND archived_at IS NULL",
            (instructions, project_id),
        )
        if result.rowcount != 1:
            raise ArchivedProjectError(f"Active project not found: {project_id}")
        self.connection.commit()

    def grant_project_folder(self, project_id: str, folder: Path, operation: str) -> str:
        self._require_active_project(project_id)
        if operation not in {"read", "write"}:
            raise ValueError("Folder grants support only read or write operations.")
        folder = folder.resolve(strict=True)
        if not folder.is_dir():
            raise ValueError("Project folder grant requires an existing directory.")
        existing = self.connection.execute(
            "SELECT id, revoked_at FROM project_folder_grants WHERE project_id = ? AND path = ? AND operation = ?",
            (project_id, str(folder), operation),
        ).fetchone()
        if existing is not None:
            if existing["revoked_at"] is not None:
                self.connection.execute("UPDATE project_folder_grants SET revoked_at = NULL, created_at = ? WHERE id = ?", (_utc_now(), existing["id"]))
                self.connection.commit()
            return str(existing["id"])
        grant_id = str(uuid.uuid4())
        self.connection.execute(
            "INSERT INTO project_folder_grants(id, project_id, path, operation, created_at) VALUES (?, ?, ?, ?, ?)",
            (grant_id, project_id, str(folder), operation, _utc_now()),
        )
        self.connection.commit()
        return grant_id

    def project_folder_grants(self, project_id: str) -> list[dict[str, object]]:
        return [dict(row) for row in self.connection.execute(
            "SELECT id, project_id, path, operation, created_at, revoked_at FROM project_folder_grants WHERE project_id = ? ORDER BY created_at, id",
            (project_id,),
        )]

    def revoke_project_folder_grant(self, grant_id: str) -> None:
        row = self.connection.execute("SELECT project_id FROM project_folder_grants WHERE id = ? AND revoked_at IS NULL", (grant_id,)).fetchone()
        if row is None:
            raise KeyError("Active project folder grant not found.")
        self._require_active_project(str(row["project_id"]))
        self.connection.execute("UPDATE project_folder_grants SET revoked_at = ? WHERE id = ?", (_utc_now(), grant_id))
        self.connection.commit()

    def authorize_project_path(self, project_id: str, target: Path, operation: str) -> bool:
        self._require_active_project(project_id)
        if operation not in {"read", "write"}:
            return False
        candidate = target.resolve(strict=False)
        for grant in self.connection.execute(
            "SELECT path FROM project_folder_grants WHERE project_id = ? AND operation = ? AND revoked_at IS NULL",
            (project_id, operation),
        ):
            try:
                candidate.relative_to(Path(grant["path"]))
                return True
            except ValueError:
                continue
        return False

    def create_session(
        self,
        project_id: str,
        title: str,
        reasoning_effort: str = "standard",
        parent_session_id: str | None = None,
    ) -> str:
        self._require_active_project(project_id)
        self._require_reasoning_effort(reasoning_effort)
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

    def set_session_reasoning_effort(self, session_id: str, reasoning_effort: str) -> None:
        self._require_reasoning_effort(reasoning_effort)
        result = self.connection.execute(
            "UPDATE sessions SET reasoning_effort = ? WHERE id = ?", (reasoning_effort, session_id)
        )
        if result.rowcount != 1:
            raise KeyError(f"Session not found: {session_id}")
        self.connection.commit()

    def search_sessions(self, query: str, project_id: str | None = None) -> list[dict[str, object]]:
        query = query.strip()
        if not query:
            raise ValueError("Session search query is required.")
        conditions = ["instr(lower(s.title), lower(?)) > 0"]
        parameters: list[object] = [query]
        if project_id is not None:
            conditions.append("s.project_id = ?")
            parameters.append(project_id)
        rows = self.connection.execute(
            f"""SELECT s.id, s.project_id, p.name AS project_name, s.title, s.parent_session_id, s.reasoning_effort, s.starred, s.created_at
                FROM sessions s JOIN projects p ON p.id = s.project_id WHERE {' AND '.join(conditions)}
                ORDER BY s.created_at DESC, s.id DESC""",
            parameters,
        )
        return [dict(row) for row in rows]

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

    def search_artifacts(self, query: str, project_id: str | None = None, media_type: str | None = None) -> list[dict[str, object]]:
        query = query.strip()
        if not query:
            raise ValueError("Artifact search query is required.")
        conditions = ["instr(lower(a.name), lower(?)) > 0"]
        parameters: list[object] = [query]
        if project_id is not None:
            conditions.append("a.project_id = ?")
            parameters.append(project_id)
        if media_type is not None:
            conditions.append("a.media_type = ?")
            parameters.append(media_type)
        rows = self.connection.execute(
            f"""SELECT a.id, a.project_id, a.session_id, a.name, a.media_type, a.created_at,
                       v.version_number AS latest_version, v.content_hash AS latest_content_hash
                FROM artifacts a LEFT JOIN artifact_versions v ON v.id = (
                    SELECT id FROM artifact_versions WHERE artifact_id = a.id ORDER BY version_number DESC LIMIT 1
                ) WHERE {' AND '.join(conditions)} ORDER BY a.created_at DESC, a.id DESC""",
            parameters,
        )
        return [dict(row) for row in rows]

    def create_job(
        self,
        project_id: str,
        operation: str,
        request: Mapping[str, object],
        session_id: str | None = None,
        parent_job_id: str | None = None,
    ) -> str:
        self._require_active_project(project_id)
        if not operation:
            raise ValueError("A job operation is required.")
        self._require_project_session(project_id, session_id)
        job_id = str(uuid.uuid4())
        self.connection.execute(
            """INSERT INTO jobs(id, project_id, session_id, parent_job_id, operation, state, request_json, created_at)
               VALUES (?, ?, ?, ?, ?, 'queued', ?, ?)""",
            (job_id, project_id, session_id, parent_job_id, operation, _json(request), _utc_now()),
        )
        self.connection.commit()
        return job_id

    def retry_job(self, job_id: str) -> dict[str, object]:
        job = self.job(job_id)
        if job["state"] not in {"failed", "cancelled"}:
            raise ValueError("Only failed or cancelled jobs can be retried.")
        retry_id = self.create_job(str(job["project_id"]), str(job["operation"]), job["request"], str(job["session_id"]) if job["session_id"] else None, job_id)
        return self.job(retry_id)

    def claim_next_job(self) -> dict[str, object] | None:
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            row = self.connection.execute(
                "SELECT * FROM jobs WHERE state = 'queued' ORDER BY created_at, id LIMIT 1"
            ).fetchone()
            if row is None:
                self.connection.commit()
                return None
            started_at = _utc_now()
            self.connection.execute(
                "UPDATE jobs SET state = 'running', started_at = ? WHERE id = ?", (started_at, row["id"])
            )
            self.connection.commit()
            return self.job(row["id"])
        except Exception:
            self.connection.rollback()
            raise

    def claim_job(self, job_id: str) -> dict[str, object]:
        result = self.connection.execute(
            "UPDATE jobs SET state = 'running', started_at = ? WHERE id = ? AND state = 'queued'",
            (_utc_now(), job_id),
        )
        if result.rowcount != 1:
            raise ValueError("Job cannot be claimed unless it is queued.")
        self.connection.commit()
        return self.job(job_id)

    def create_generation(
        self,
        project_id: str,
        runtime: str,
        model: str,
        prompt: str,
        session_id: str | None = None,
    ) -> str:
        if not runtime.strip() or not model.strip() or not prompt.strip():
            raise ValueError("Generation runtime, model, and prompt are required.")
        job_id = self.create_job(project_id, "model.generate", {"runtime": runtime, "model": model, "prompt": prompt}, session_id)
        generation_id = str(uuid.uuid4())
        self.connection.execute(
            "INSERT INTO generations(id, job_id, runtime, model, prompt, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (generation_id, job_id, runtime, model, prompt, _utc_now()),
        )
        self.connection.commit()
        return generation_id

    def append_generation_chunk(self, generation_id: str, content: str) -> None:
        if not content:
            return
        generation = self.generation(generation_id)
        if generation["state"] != "running":
            raise ValueError("Generation can receive chunks only while running.")
        sequence = len(generation["chunks"])
        self.connection.execute(
            "INSERT INTO generation_chunks(generation_id, sequence_number, content, created_at) VALUES (?, ?, ?, ?)",
            (generation_id, sequence, content, _utc_now()),
        )
        self.connection.commit()

    def generation(self, generation_id: str) -> dict[str, object]:
        row = self.connection.execute(
            """SELECT g.id, g.job_id, g.runtime, g.model, g.prompt, g.created_at,
                      j.project_id, j.session_id, j.state, j.result_json, j.diagnostic_json
               FROM generations g JOIN jobs j ON j.id = g.job_id WHERE g.id = ?""",
            (generation_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Generation not found: {generation_id}")
        chunks = [str(chunk["content"]) for chunk in self.connection.execute(
            "SELECT content FROM generation_chunks WHERE generation_id = ? ORDER BY sequence_number", (generation_id,)
        )]
        return {
            "id": row["id"], "job_id": row["job_id"], "project_id": row["project_id"], "session_id": row["session_id"],
            "runtime": row["runtime"], "model": row["model"], "prompt": row["prompt"], "state": row["state"],
            "chunks": chunks, "output": "".join(chunks), "result": json.loads(row["result_json"]) if row["result_json"] else None,
            "diagnostic": json.loads(row["diagnostic_json"]) if row["diagnostic_json"] else None,
        }

    def generations(self, project_id: str | None = None) -> list[dict[str, object]]:
        where = "WHERE j.project_id = ?" if project_id is not None else ""
        parameters: tuple[str, ...] = (project_id,) if project_id is not None else ()
        rows = self.connection.execute(
            f"SELECT g.id FROM generations g JOIN jobs j ON j.id = g.job_id {where} ORDER BY g.created_at DESC, g.id DESC",
            parameters,
        )
        return [self.generation(str(row["id"])) for row in rows]

    def request_cancellation(self, job_id: str) -> dict[str, object]:
        job = self.job(job_id)
        if job["state"] == "queued":
            self._set_job_state(job_id, "cancelled", completed_at=_utc_now())
        elif job["state"] == "running":
            self._set_job_state(job_id, "cancel_requested")
        else:
            raise ValueError(f"Job cannot be cancelled from state: {job['state']}")
        return self.job(job_id)

    def complete_job(self, job_id: str, result: Mapping[str, object]) -> dict[str, object]:
        job = self.job(job_id)
        if job["state"] == "running":
            self._set_job_state(job_id, "succeeded", result=result, completed_at=_utc_now())
        elif job["state"] == "cancel_requested":
            self._set_job_state(job_id, "cancelled", completed_at=_utc_now())
        else:
            raise ValueError(f"Job cannot complete from state: {job['state']}")
        return self.job(job_id)

    def fail_job(self, job_id: str, diagnostic: Mapping[str, object]) -> dict[str, object]:
        job = self.job(job_id)
        if job["state"] not in {"running", "cancel_requested"}:
            raise ValueError(f"Job cannot fail from state: {job['state']}")
        self._set_job_state(job_id, "failed", diagnostic=diagnostic, completed_at=_utc_now())
        return self.job(job_id)

    def append_job_event(self, job_id: str, kind: str, detail: Mapping[str, object]) -> None:
        job = self.job(job_id)
        if job["state"] not in {"running", "cancel_requested"}:
            raise ValueError("Job events can only be appended while a job is active.")
        if not kind.strip():
            raise ValueError("A job event kind is required.")
        sequence_number = self.connection.execute(
            "SELECT COALESCE(MAX(sequence_number), -1) + 1 AS sequence_number FROM job_events WHERE job_id = ?",
            (job_id,),
        ).fetchone()["sequence_number"]
        self.connection.execute(
            "INSERT INTO job_events(id, job_id, sequence_number, kind, detail_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), job_id, sequence_number, kind, _json(detail), _utc_now()),
        )
        self.connection.commit()

    def job_events(self, job_id: str) -> list[dict[str, object]]:
        if self.connection.execute("SELECT 1 FROM jobs WHERE id = ?", (job_id,)).fetchone() is None:
            raise KeyError(f"Job not found: {job_id}")
        rows = self.connection.execute(
            "SELECT id, sequence_number, kind, detail_json, created_at FROM job_events WHERE job_id = ? ORDER BY sequence_number",
            (job_id,),
        )
        return [
            {"id": row["id"], "sequence_number": row["sequence_number"], "kind": row["kind"], "detail": json.loads(row["detail_json"]), "created_at": row["created_at"]}
            for row in rows
        ]

    def job(self, job_id: str) -> dict[str, object]:
        row = self.connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(f"Job not found: {job_id}")
        record = _job_record(row)
        record["events"] = self.job_events(job_id)
        return record

    def _set_job_state(
        self,
        job_id: str,
        state: str,
        *,
        result: Mapping[str, object] | None = None,
        diagnostic: Mapping[str, object] | None = None,
        completed_at: str | None = None,
    ) -> None:
        self.connection.execute(
            """UPDATE jobs SET state = ?, result_json = COALESCE(?, result_json),
               diagnostic_json = COALESCE(?, diagnostic_json), completed_at = COALESCE(?, completed_at)
               WHERE id = ?""",
            (state, _json(result) if result is not None else None, _json(diagnostic) if diagnostic is not None else None, completed_at, job_id),
        )
        self.connection.commit()

    def _require_project_session(self, project_id: str, session_id: str | None) -> None:
        if session_id is None:
            return
        session = self.connection.execute(
            "SELECT project_id FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if session is None or session["project_id"] != project_id:
            raise ValueError("A job session must belong to its project.")

    def _require_reasoning_effort(self, reasoning_effort: str) -> None:
        if reasoning_effort not in _REASONING_EFFORTS:
            raise ValueError("Unsupported session reasoning effort.")

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


def _job_record(row: sqlite3.Row) -> dict[str, object]:
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "session_id": row["session_id"],
        "parent_job_id": row["parent_job_id"],
        "operation": row["operation"],
        "state": row["state"],
        "request": json.loads(row["request_json"]),
        "result": json.loads(row["result_json"]) if row["result_json"] else None,
        "diagnostic": json.loads(row["diagnostic_json"]) if row["diagnostic_json"] else None,
    }
