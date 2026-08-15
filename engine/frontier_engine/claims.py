"""Typed scientific claims with exact evidence links."""

from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path


_TYPES = {"source", "observation", "computed", "inference", "hypothesis"}
_STATUSES = {"draft", "supported", "disputed", "retracted"}


class ClaimLedger:
    def __init__(self, database_path: Path) -> None:
        self.connection = sqlite3.connect(database_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS scientific_claims (id TEXT PRIMARY KEY, claim_type TEXT NOT NULL, status TEXT NOT NULL, text TEXT NOT NULL, uncertainty TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS claim_evidence (claim_id TEXT NOT NULL REFERENCES scientific_claims(id), evidence_uri TEXT NOT NULL, selector TEXT NOT NULL, PRIMARY KEY (claim_id, evidence_uri, selector));
        """)
        self.connection.commit()

    def close(self) -> None: self.connection.close()

    def create(self, claim_type: str, text: str, uncertainty: str, evidence: list[tuple[str, str]]) -> str:
        if claim_type not in _TYPES or not text.strip() or not uncertainty.strip(): raise ValueError("Claim type, text, and uncertainty are required.")
        claim_id = str(uuid.uuid4())
        self.connection.execute("INSERT INTO scientific_claims VALUES (?, ?, 'draft', ?, ?)", (claim_id, claim_type, text, uncertainty))
        self.connection.executemany("INSERT INTO claim_evidence VALUES (?, ?, ?)", [(claim_id, uri, selector) for uri, selector in evidence])
        self.connection.commit()
        return claim_id

    def set_status(self, claim_id: str, status: str) -> None:
        if status not in _STATUSES: raise ValueError("Unsupported claim status.")
        if self.connection.execute("UPDATE scientific_claims SET status = ? WHERE id = ?", (status, claim_id)).rowcount != 1: raise KeyError("Claim not found.")
        self.connection.commit()

    def list(self) -> list[dict[str, object]]:
        claims = [dict(row) for row in self.connection.execute("SELECT * FROM scientific_claims")]
        for claim in claims:
            claim["evidence"] = [dict(row) for row in self.connection.execute("SELECT evidence_uri, selector FROM claim_evidence WHERE claim_id = ?", (claim["id"],))]
        return claims
