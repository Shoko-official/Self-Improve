"""Version-targeted annotations that cannot silently move with an artifact."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

_TARGETS = {"text", "code", "markdown", "latex", "pdf_region", "image_point", "html_element", "transcript_region"}

@dataclass(frozen=True)
class Annotation:
    id: str; artifact_version_id: str; target_kind: str; selector: dict[str, object]; body: str; consumed_at: str | None

class AnnotationStore:
 def __init__(self, database: Path) -> None:
  self.connection=sqlite3.connect(database); self.connection.row_factory=sqlite3.Row
  self.connection.execute("CREATE TABLE IF NOT EXISTS annotations(id TEXT PRIMARY KEY, artifact_version_id TEXT NOT NULL, target_kind TEXT NOT NULL, selector_json TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL, consumed_at TEXT)"); self.connection.commit()
 def close(self) -> None: self.connection.close()
 def create(self, artifact_version_id: str, target_kind: str, selector: dict[str, object], body: str) -> str:
  if target_kind not in _TARGETS: raise ValueError("Unsupported annotation target")
  if not body.strip(): raise ValueError("Annotation body is required")
  identifier=str(uuid.uuid4()); self.connection.execute("INSERT INTO annotations VALUES (?, ?, ?, ?, ?, ?, NULL)",(identifier,artifact_version_id,target_kind,json.dumps(selector,sort_keys=True),body,_now())); self.connection.commit(); return identifier
 def list_open(self, artifact_version_id: str) -> tuple[Annotation,...]:
  rows=self.connection.execute("SELECT * FROM annotations WHERE artifact_version_id=? AND consumed_at IS NULL ORDER BY created_at",(artifact_version_id,)).fetchall(); return tuple(_row(row) for row in rows)
 def consume(self, annotation_ids: tuple[str,...]) -> tuple[Annotation,...]:
  if not annotation_ids: return ()
  marks=",".join("?" for _ in annotation_ids); rows=self.connection.execute(f"SELECT * FROM annotations WHERE id IN ({marks}) AND consumed_at IS NULL",annotation_ids).fetchall()
  if len(rows)!=len(annotation_ids): raise ValueError("Annotations must be open before consumption")
  self.connection.execute(f"UPDATE annotations SET consumed_at=? WHERE id IN ({marks})",(_now(),*annotation_ids)); self.connection.commit(); return tuple(_row(row) for row in rows)
def _row(row: sqlite3.Row) -> Annotation: return Annotation(row["id"],row["artifact_version_id"],row["target_kind"],json.loads(row["selector_json"]),row["body"],row["consumed_at"])
def _now() -> str: return datetime.now(UTC).isoformat()
