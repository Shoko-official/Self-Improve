"""Durable local model file registry without executable-capability claims."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from collections.abc import Callable
from typing import Any


class HuggingFaceHubError(RuntimeError):
    pass


class HuggingFaceHub:
    """Explicit public Hub discovery and file transfer without runtime claims."""

    def __init__(self, base_url: str = "https://huggingface.co", timeout_seconds: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def search_models(self, query: str, limit: int = 10) -> list[dict[str, object]]:
        if not query.strip():
            raise ValueError("A Hugging Face model search query is required.")
        if not 1 <= limit <= 50:
            raise ValueError("Hugging Face model search limit must be between 1 and 50.")
        payload = self._json(f"/api/models?{urllib.parse.urlencode({'search': query, 'limit': limit, 'full': 'false'})}")
        if not isinstance(payload, list):
            raise HuggingFaceHubError("FR-HF-SEARCH: Hub returned a non-list response")
        return [{key: item.get(key) for key in ("modelId", "sha", "lastModified", "downloads", "likes", "library_name", "tags")} for item in payload if isinstance(item, dict) and isinstance(item.get("modelId"), str)]

    def download_file(self, repository_id: str, filename: str, destination: Path, revision: str = "main", expected_sha256: str | None = None, cancel_requested: Callable[[], bool] | None = None) -> dict[str, object]:
        if not _valid_repository_id(repository_id) or not _valid_revision(revision) or not _valid_filename(filename):
            raise ValueError("Invalid Hugging Face repository, revision, or filename.")
        destination = destination.resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.part")
        digest = hashlib.sha256()
        received = 0
        url = f"{self.base_url}/{urllib.parse.quote(repository_id, safe='/')}/resolve/{urllib.parse.quote(revision, safe='')}/{urllib.parse.quote(filename, safe='/')}"
        try:
            with urllib.request.urlopen(url, timeout=self.timeout_seconds) as response, temporary.open("wb") as target:
                while True:
                    if cancel_requested is not None and cancel_requested():
                        raise HuggingFaceHubError("FR-HF-DOWNLOAD-CANCELLED")
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    target.write(chunk)
                    digest.update(chunk)
                    received += len(chunk)
            actual_sha256 = digest.hexdigest()
            if expected_sha256 is not None and actual_sha256 != expected_sha256.lower():
                raise HuggingFaceHubError("FR-HF-SHA256-MISMATCH")
            os.replace(temporary, destination)
            return {"repository_id": repository_id, "revision": revision, "filename": filename, "path": str(destination), "bytes": received, "sha256": actual_sha256}
        except (OSError, urllib.error.URLError, urllib.error.HTTPError) as error:
            raise HuggingFaceHubError(f"FR-HF-DOWNLOAD: {error}") from error
        finally:
            if temporary.exists():
                temporary.unlink()

    def _json(self, path: str) -> Any:
        try:
            with urllib.request.urlopen(f"{self.base_url}{path}", timeout=self.timeout_seconds) as response:
                return json.loads(response.read())
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as error:
            raise HuggingFaceHubError(f"FR-HF-SEARCH: {error}") from error


def _valid_repository_id(value: str) -> bool:
    parts = value.split("/")
    return len(parts) == 2 and all(part and all(character.isalnum() or character in "-_." for character in part) for part in parts)


def _valid_revision(value: str) -> bool:
    return bool(value) and all(character.isalnum() or character in "-_." for character in value)


def _valid_filename(value: str) -> bool:
    path = Path(value)
    return bool(value) and not path.is_absolute() and ".." not in path.parts


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

    def download_and_register(self, hub: HuggingFaceHub, repository_id: str, filename: str, destination: Path, revision: str = "main", expected_sha256: str | None = None, cancel_requested: Callable[[], bool] | None = None) -> dict[str, object]:
        transfer = hub.download_file(repository_id, filename, destination, revision, expected_sha256, cancel_requested)
        return {"transfer": transfer, "model": self.register(destination)}
