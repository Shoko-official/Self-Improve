"""Durable, exact-scope permission decisions for Frontier actions."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path


class PermissionLedger:
    def __init__(self, database: Path) -> None:
        self.connection = sqlite3.connect(database)
        self.connection.execute("""CREATE TABLE IF NOT EXISTS permission_grants(
            id TEXT PRIMARY KEY, resource TEXT NOT NULL, operation TEXT NOT NULL, scope TEXT NOT NULL,
            expires_at TEXT, revoked_at TEXT, used_at TEXT, created_at TEXT NOT NULL)""")
        self.connection.commit()

    def close(self) -> None: self.connection.close()

    def grant(self, resource: str, operation: str, scope: str = "once", expires_at: str | None = None) -> str:
        if scope not in {"once", "session", "project", "global", "until_revoked"}: raise ValueError("Invalid permission scope")
        grant_id = str(uuid.uuid4())
        self.connection.execute("INSERT INTO permission_grants VALUES (?, ?, ?, ?, ?, NULL, NULL, ?)", (grant_id, resource, operation, scope, expires_at, _now()))
        self.connection.commit(); return grant_id

    def revoke(self, grant_id: str) -> None:
        if self.connection.execute("UPDATE permission_grants SET revoked_at=? WHERE id=? AND revoked_at IS NULL", (_now(), grant_id)).rowcount != 1: raise KeyError("Active grant not found")
        self.connection.commit()

    def authorize(self, resource: str, operation: str) -> bool:
        row = self.connection.execute("""SELECT id, scope FROM permission_grants WHERE resource=? AND operation=?
            AND revoked_at IS NULL AND (expires_at IS NULL OR expires_at > ?) AND (scope != 'once' OR used_at IS NULL)
            ORDER BY created_at DESC LIMIT 1""", (resource, operation, _now())).fetchone()
        if row is None: return False
        if row[1] == "once": self.connection.execute("UPDATE permission_grants SET used_at=? WHERE id=?", (_now(), row[0])); self.connection.commit()
        return True

def _now() -> str: return datetime.now(UTC).isoformat()
