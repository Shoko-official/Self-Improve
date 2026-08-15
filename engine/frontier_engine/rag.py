"""Durable retrieval with exact source citations and optional real embeddings."""

from __future__ import annotations

import json
import math
import re
import sqlite3
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class Embedder(Protocol):
    """A runtime-pack or provider-backed embedding implementation."""

    def embed(self, text: str) -> Sequence[float]: ...


@dataclass(frozen=True)
class Citation:
    chunk_id: str
    source_uri: str
    source_label: str
    text: str
    start_offset: int
    end_offset: int
    score: float
    retrieval_mode: str


class HybridIndex:
    """SQLite FTS5 retrieval plus an optional supplied embedding implementation."""

    def __init__(self, database_path: Path, embedder: Embedder | None = None) -> None:
        self.connection = sqlite3.connect(database_path)
        self.connection.row_factory = sqlite3.Row
        self.embedder = embedder
        self._migrate()

    def close(self) -> None:
        self.connection.close()

    @property
    def retrieval_mode(self) -> str:
        return "hybrid" if self.embedder is not None else "lexical"

    def _migrate(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS rag_sources (
                id TEXT PRIMARY KEY,
                source_uri TEXT NOT NULL,
                source_label TEXT NOT NULL,
                source_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS rag_chunks (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL REFERENCES rag_sources(id),
                text TEXT NOT NULL,
                start_offset INTEGER NOT NULL,
                end_offset INTEGER NOT NULL,
                embedding_json TEXT
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS rag_chunks_fts USING fts5(chunk_id UNINDEXED, text);
            """
        )
        self.connection.commit()

    def ingest(self, source_uri: str, source_label: str, text: str) -> list[str]:
        if not text.strip():
            raise ValueError("Cannot ingest an empty source.")
        source_id = str(uuid.uuid4())
        source_hash = _sha256(text.encode())
        self.connection.execute(
            "INSERT INTO rag_sources(id, source_uri, source_label, source_hash, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
            (source_id, source_uri, source_label, source_hash),
        )
        chunk_ids: list[str] = []
        for chunk_text, start_offset, end_offset in _chunks(text):
            chunk_id = str(uuid.uuid4())
            embedding = list(self.embedder.embed(chunk_text)) if self.embedder is not None else None
            self.connection.execute(
                """INSERT INTO rag_chunks(id, source_id, text, start_offset, end_offset, embedding_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (chunk_id, source_id, chunk_text, start_offset, end_offset, json.dumps(embedding) if embedding else None),
            )
            self.connection.execute("INSERT INTO rag_chunks_fts(chunk_id, text) VALUES (?, ?)", (chunk_id, chunk_text))
            chunk_ids.append(chunk_id)
        self.connection.commit()
        return chunk_ids

    def search(self, query: str, limit: int = 5) -> list[Citation]:
        if limit < 1:
            raise ValueError("Search limit must be positive.")
        terms = re.findall(r"[\w-]+", query, flags=re.UNICODE)
        if not terms:
            return []
        lexical_rows = self.connection.execute(
            """SELECT rag_chunks_fts.chunk_id, bm25(rag_chunks_fts) AS rank
               FROM rag_chunks_fts WHERE rag_chunks_fts MATCH ? ORDER BY rank LIMIT ?""",
            (" OR ".join(terms), limit * 4),
        ).fetchall()
        lexical_scores = {row["chunk_id"]: 1 / (1 + max(row["rank"], 0)) for row in lexical_rows}
        vector_scores = self._vector_scores(query) if self.embedder is not None else {}
        ranked_ids = sorted(
            set(lexical_scores) | set(vector_scores),
            key=lambda chunk_id: lexical_scores.get(chunk_id, 0) + vector_scores.get(chunk_id, 0),
            reverse=True,
        )[:limit]
        if not ranked_ids:
            return []
        placeholders = ",".join("?" for _ in ranked_ids)
        rows = self.connection.execute(
            f"""SELECT chunks.id, sources.source_uri, sources.source_label, chunks.text,
                       chunks.start_offset, chunks.end_offset
                FROM rag_chunks AS chunks JOIN rag_sources AS sources ON sources.id = chunks.source_id
                WHERE chunks.id IN ({placeholders})""",
            ranked_ids,
        ).fetchall()
        records = {row["id"]: row for row in rows}
        return [
            Citation(
                chunk_id=chunk_id,
                source_uri=records[chunk_id]["source_uri"],
                source_label=records[chunk_id]["source_label"],
                text=records[chunk_id]["text"],
                start_offset=records[chunk_id]["start_offset"],
                end_offset=records[chunk_id]["end_offset"],
                score=lexical_scores.get(chunk_id, 0) + vector_scores.get(chunk_id, 0),
                retrieval_mode=self.retrieval_mode,
            )
            for chunk_id in ranked_ids
        ]

    def evaluate(self, cases: Iterable[tuple[str, set[str]]], limit: int = 5) -> dict[str, float | int]:
        cases = list(cases)
        hits = sum(
            bool({result.source_uri for result in self.search(query, limit)} & expected_sources)
            for query, expected_sources in cases
        )
        return {"cases": len(cases), "hits": hits, "recall_at_k": hits / len(cases) if cases else 0.0}

    def _vector_scores(self, query: str) -> dict[str, float]:
        query_vector = list(self.embedder.embed(query))
        rows = self.connection.execute(
            "SELECT id, embedding_json FROM rag_chunks WHERE embedding_json IS NOT NULL"
        ).fetchall()
        return {
            row["id"]: _cosine(query_vector, json.loads(row["embedding_json"]))
            for row in rows
        }


def _chunks(text: str) -> list[tuple[str, int, int]]:
    matches = list(re.finditer(r"\S(?:.*?\S)?(?=\n\s*\n|\Z)", text, flags=re.DOTALL))
    return [(match.group(), match.start(), match.end()) for match in matches]


def _sha256(value: bytes) -> str:
    import hashlib

    return hashlib.sha256(value).hexdigest()


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("Embedding dimensions must match and cannot be empty.")
    denominator = math.sqrt(sum(value * value for value in left)) * math.sqrt(sum(value * value for value in right))
    return sum(a * b for a, b in zip(left, right)) / denominator if denominator else 0.0
