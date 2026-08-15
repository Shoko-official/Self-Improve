"""Durable local model file registry without executable-capability claims."""

from __future__ import annotations

import hashlib
import sqlite3
import uuid
from pathlib import Path


class ModelRegistry:
    def __init__(self, database_path: Path) -> None:
        self.connection = sqlite3.connect(database_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("CREATE TABLE IF NOT EXISTS local_models (id TEXT PRIMARY KEY, path TEXT UNIQUE NOT NULL, sha256 TEXT NOT NULL, bytes INTEGER NOT NULL, format TEXT NOT NULL, capability_state TEXT NOT NULL)")
        self.connection.commit()

    def close(self) -> None: self.connection.close()

    def register(self, path: Path) -> dict[str, object]:
        path = path.resolve()
        if not path.is_file(): raise FileNotFoundError(f"Model file not found: {path}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        extension = path.suffix.removeprefix(".").lower() or "unknown"
        record = {"id": str(uuid.uuid4()), "path": str(path), "sha256": digest, "bytes": path.stat().st_size, "format": extension, "capability_state": "unvalidated"}
        self.connection.execute("INSERT INTO local_models VALUES (:id, :path, :sha256, :bytes, :format, :capability_state)", record); self.connection.commit()
        return record

    def list(self) -> list[dict[str, object]]:
        return [dict(row) for row in self.connection.execute("SELECT * FROM local_models ORDER BY path")]
