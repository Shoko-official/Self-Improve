"""Durable, source-scoped literature evidence records."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path


def _now() -> str:
    return datetime.now(UTC).isoformat()


class LiteratureStore:
    """Records reproducible queries and inspected evidence without fetching remotely."""

    def __init__(self, database_path: Path) -> None:
        self.connection = sqlite3.connect(database_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS literature_queries (id TEXT PRIMARY KEY, query_text TEXT NOT NULL, source TEXT NOT NULL, filters_json TEXT NOT NULL, accessed_at TEXT NOT NULL, result_count INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS literature_evidence (id TEXT PRIMARY KEY, query_id TEXT NOT NULL REFERENCES literature_queries(id), stable_id TEXT NOT NULL, title TEXT NOT NULL, full_text_route TEXT, version_state TEXT NOT NULL, retraction_state TEXT NOT NULL, retained_evidence TEXT NOT NULL, created_at TEXT NOT NULL);
        """)
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def record_query(self, query_text: str, source: str, filters_json: str, result_count: int) -> str:
        if not query_text.strip() or not source.strip() or result_count < 0:
            raise ValueError("Query text, source, and a non-negative result count are required.")
        query_id = str(uuid.uuid4())
        self.connection.execute("INSERT INTO literature_queries VALUES (?, ?, ?, ?, ?, ?)", (query_id, query_text, source, filters_json, _now(), result_count))
        self.connection.commit()
        return query_id

    def record_evidence(self, query_id: str, stable_id: str, title: str, retained_evidence: str, full_text_route: str | None = None, version_state: str = "unknown", retraction_state: str = "unknown") -> str:
        if not stable_id.strip() or not title.strip() or not retained_evidence.strip():
            raise ValueError("Stable identifier, title, and retained evidence are required.")
        evidence_id = str(uuid.uuid4())
        self.connection.execute("INSERT INTO literature_evidence VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (evidence_id, query_id, stable_id, title, full_text_route, version_state, retraction_state, retained_evidence, _now()))
        self.connection.commit()
        return evidence_id

    def queries(self) -> list[dict[str, object]]:
        return [dict(row) for row in self.connection.execute("SELECT * FROM literature_queries ORDER BY accessed_at DESC")]

    def evidence(self, query_id: str) -> list[dict[str, object]]:
        return [dict(row) for row in self.connection.execute("SELECT * FROM literature_evidence WHERE query_id = ? ORDER BY created_at", (query_id,))]
