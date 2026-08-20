"""Durable local model file registry without executable-capability claims."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
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

    def download_plan(self, repository_id: str, filename: str, destination: Path, revision: str = "main", interactive: bool = False) -> dict[str, object]:
        url = self._download_url(repository_id, filename, revision)
        destination = destination.resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(url, method="HEAD")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                content_length = int(response.headers.get("Content-Length", "0")) or None
                accepts_ranges = response.headers.get("Accept-Ranges", "").lower() == "bytes"
                etag = response.headers.get("ETag")
        except (OSError, urllib.error.URLError, urllib.error.HTTPError) as error:
            raise HuggingFaceHubError(f"FR-HF-PLAN: {error}") from error
        free_bytes = shutil.disk_usage(destination.parent).free
        xet_available = self._xet_available()
        accelerator = "huggingface-cache" if xet_available and not interactive else "parallel-http" if accepts_ranges and content_length is not None and content_length >= 4 * 1024 * 1024 else "http"
        required_free_bytes = content_length * 2 if content_length is not None and accelerator == "parallel-http" else content_length
        return {
            "repository_id": repository_id,
            "revision": revision,
            "filename": filename,
            "url": url,
            "destination": str(destination),
            "bytes": content_length,
            "accepts_ranges": accepts_ranges,
            "etag": etag,
            "free_bytes": free_bytes,
            "required_free_bytes": required_free_bytes,
            "fits": required_free_bytes is None or free_bytes >= required_free_bytes,
            "accelerator": accelerator,
            "xet_available": xet_available,
            "interactive": interactive,
        }

    def download_file(self, repository_id: str, filename: str, destination: Path, revision: str = "main", expected_sha256: str | None = None, cancel_requested: Callable[[], bool] | None = None, progress: Callable[[int, int | None], None] | None = None, workers: int = 4) -> dict[str, object]:
        if not _valid_repository_id(repository_id) or not _valid_revision(revision) or not _valid_filename(filename):
            raise ValueError("Invalid Hugging Face repository, revision, or filename.")
        if not 1 <= workers <= 16:
            raise ValueError("Download workers must be between 1 and 16.")
        destination = destination.resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        url = self._download_url(repository_id, filename, revision)
        started = time.monotonic()
        interactive = cancel_requested is not None or progress is not None
        plan = self.download_plan(repository_id, filename, destination, revision, interactive)
        if plan["bytes"] is not None and not plan["fits"]:
            raise HuggingFaceHubError("FR-HF-DISK-SPACE")
        if plan["accelerator"] == "huggingface-cache":
            transfer = self._download_with_hf_cache(repository_id, filename, destination, revision, expected_sha256)
            transfer["elapsed_seconds"] = time.monotonic() - started
            transfer["bytes_per_second"] = int(transfer["bytes"] / max(float(transfer["elapsed_seconds"]), 0.001))
            return transfer
        if plan["accepts_ranges"] and isinstance(plan["bytes"], int) and plan["bytes"] >= 4 * 1024 * 1024 and workers > 1:
            return self._download_parallel(url, repository_id, revision, filename, destination, plan["bytes"], expected_sha256, cancel_requested, progress, workers, started)
        temporary = destination.with_name(f".{destination.name}.part")
        digest = hashlib.sha256()
        received = 0
        try:
            with urllib.request.urlopen(url, timeout=self.timeout_seconds) as response, temporary.open("wb") as target:
                total = int(response.headers.get("Content-Length", "0")) or None
                while True:
                    if cancel_requested is not None and cancel_requested():
                        raise HuggingFaceHubError("FR-HF-DOWNLOAD-CANCELLED")
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    target.write(chunk)
                    digest.update(chunk)
                    received += len(chunk)
                    if progress is not None:
                        progress(received, total)
            actual_sha256 = digest.hexdigest()
            if expected_sha256 is not None and actual_sha256 != expected_sha256.lower():
                raise HuggingFaceHubError("FR-HF-SHA256-MISMATCH")
            os.replace(temporary, destination)
            elapsed = time.monotonic() - started
            return {"repository_id": repository_id, "revision": revision, "filename": filename, "path": str(destination), "bytes": received, "sha256": actual_sha256, "method": "http", "segments": 1, "resumed_bytes": 0, "elapsed_seconds": elapsed, "bytes_per_second": int(received / max(elapsed, 0.001))}
        except (OSError, urllib.error.URLError, urllib.error.HTTPError) as error:
            raise HuggingFaceHubError(f"FR-HF-DOWNLOAD: {error}") from error
        finally:
            if temporary.exists():
                temporary.unlink()

    def _download_parallel(self, url: str, repository_id: str, revision: str, filename: str, destination: Path, total: int, expected_sha256: str | None, cancel_requested: Callable[[], bool] | None, progress: Callable[[int, int | None], None] | None, workers: int, started: float) -> dict[str, object]:
        segment_count = min(workers, max(2, (total + 8 * 1024 * 1024 - 1) // (8 * 1024 * 1024)))
        segment_size = (total + segment_count - 1) // segment_count
        parts = [destination.with_name(f".{destination.name}.part.{index:02d}") for index in range(segment_count)]
        ranges = [(index * segment_size, min(total - 1, (index + 1) * segment_size - 1)) for index in range(segment_count)]
        resumed = sum(min(part.stat().st_size, end - start + 1) for part, (start, end) in zip(parts, ranges) if part.exists())

        def transfer_segment(index: int) -> int:
            part = parts[index]
            start, end = ranges[index]
            existing = part.stat().st_size if part.exists() else 0
            expected = end - start + 1
            if existing > expected:
                part.unlink()
                existing = 0
            if existing == expected:
                return existing
            request = urllib.request.Request(url, headers={"Range": f"bytes={start + existing}-{end}"})
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response, part.open("ab") as target:
                if response.status != 206:
                    raise HuggingFaceHubError("FR-HF-RANGE-UNSUPPORTED")
                written = existing
                while written < expected:
                    if cancel_requested is not None and cancel_requested():
                        raise HuggingFaceHubError("FR-HF-DOWNLOAD-CANCELLED")
                    chunk = response.read(min(1024 * 1024, expected - written))
                    if not chunk:
                        break
                    target.write(chunk)
                    written += len(chunk)
                    if progress is not None:
                        progress(sum(min(item.stat().st_size, item_end - item_start + 1) for item, (item_start, item_end) in zip(parts, ranges) if item.exists()), total)
            if written != expected:
                raise HuggingFaceHubError("FR-HF-RANGE-INCOMPLETE")
            return written

        temporary = destination.with_name(f".{destination.name}.part")
        try:
            with ThreadPoolExecutor(max_workers=segment_count, thread_name_prefix="model-download") as pool:
                list(pool.map(transfer_segment, range(segment_count)))
            digest = hashlib.sha256()
            received = 0
            with temporary.open("wb") as target:
                for part in parts:
                    with part.open("rb") as source:
                        for chunk in iter(lambda: source.read(1024 * 1024), b""):
                            if cancel_requested is not None and cancel_requested():
                                raise HuggingFaceHubError("FR-HF-DOWNLOAD-CANCELLED")
                            target.write(chunk)
                            digest.update(chunk)
                            received += len(chunk)
            actual_sha256 = digest.hexdigest()
            if received != total:
                raise HuggingFaceHubError("FR-HF-DOWNLOAD-SIZE-MISMATCH")
            if expected_sha256 is not None and actual_sha256 != expected_sha256.lower():
                raise HuggingFaceHubError("FR-HF-SHA256-MISMATCH")
            os.replace(temporary, destination)
            for part in parts:
                part.unlink(missing_ok=True)
            elapsed = time.monotonic() - started
            return {"repository_id": repository_id, "revision": revision, "filename": filename, "path": str(destination), "bytes": received, "sha256": actual_sha256, "method": "parallel-http", "segments": segment_count, "resumed_bytes": resumed, "elapsed_seconds": elapsed, "bytes_per_second": int(received / max(elapsed, 0.001))}
        except (OSError, urllib.error.URLError, urllib.error.HTTPError) as error:
            raise HuggingFaceHubError(f"FR-HF-DOWNLOAD: {error}") from error
        finally:
            temporary.unlink(missing_ok=True)

    def _download_with_hf_cache(self, repository_id: str, filename: str, destination: Path, revision: str, expected_sha256: str | None) -> dict[str, object]:
        from huggingface_hub import hf_hub_download

        cached = Path(hf_hub_download(repo_id=repository_id, filename=filename, revision=revision))
        temporary = destination.with_name(f".{destination.name}.part")
        digest = hashlib.sha256()
        received = 0
        try:
            with cached.open("rb") as source, temporary.open("wb") as target:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    target.write(chunk)
                    digest.update(chunk)
                    received += len(chunk)
            actual_sha256 = digest.hexdigest()
            if expected_sha256 is not None and actual_sha256 != expected_sha256.lower():
                raise HuggingFaceHubError("FR-HF-SHA256-MISMATCH")
            os.replace(temporary, destination)
            return {"repository_id": repository_id, "revision": revision, "filename": filename, "path": str(destination), "bytes": received, "sha256": actual_sha256, "method": "huggingface-cache", "xet_available": True, "segments": None, "resumed_bytes": 0}
        finally:
            temporary.unlink(missing_ok=True)

    def _download_url(self, repository_id: str, filename: str, revision: str) -> str:
        if not _valid_repository_id(repository_id) or not _valid_revision(revision) or not _valid_filename(filename):
            raise ValueError("Invalid Hugging Face repository, revision, or filename.")
        return f"{self.base_url}/{urllib.parse.quote(repository_id, safe='/')}/resolve/{urllib.parse.quote(revision, safe='')}/{urllib.parse.quote(filename, safe='/')}"

    def _xet_available(self) -> bool:
        return self.base_url == "https://huggingface.co" and importlib.util.find_spec("huggingface_hub") is not None and importlib.util.find_spec("hf_xet") is not None

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
        return self._register_verified(path, _sha256_file(path))

    def reference_external(self, path: Path) -> dict[str, object]:
        path = path.resolve()
        if not path.is_file() or path.suffix.lower() != ".gguf":
            raise ValueError("FR-MODEL-REFERENCE: an existing GGUF file is required")
        existing = self.connection.execute("SELECT * FROM local_models WHERE path = ?", (str(path),)).fetchone()
        if existing is not None:
            return dict(existing)
        record = {"id": str(uuid.uuid4()), "path": str(path), "sha256": "pending-first-load", "bytes": path.stat().st_size, "format": "gguf", "capability_state": "external-reference"}
        self.connection.execute("INSERT INTO local_models VALUES (:id, :path, :sha256, :bytes, :format, :capability_state)", record)
        self.connection.commit()
        return record

    def _register_verified(self, path: Path, digest: str) -> dict[str, object]:
        extension = path.suffix.removeprefix(".").lower() or "unknown"
        record = {"id": str(uuid.uuid4()), "path": str(path), "sha256": digest, "bytes": path.stat().st_size, "format": extension, "capability_state": "unvalidated"}
        self.connection.execute("INSERT INTO local_models VALUES (:id, :path, :sha256, :bytes, :format, :capability_state)", record); self.connection.commit()
        return record

    def list(self) -> list[dict[str, object]]:
        return [dict(row) for row in self.connection.execute("SELECT * FROM local_models ORDER BY path")]

    def download_and_register(self, hub: HuggingFaceHub, repository_id: str, filename: str, destination: Path, revision: str = "main", expected_sha256: str | None = None, cancel_requested: Callable[[], bool] | None = None, progress: Callable[[int, int | None], None] | None = None, registration_allowed: Callable[[], bool] | None = None) -> dict[str, object]:
        transfer = hub.download_file(repository_id, filename, destination, revision, expected_sha256, cancel_requested, progress)
        if (cancel_requested is not None and cancel_requested()) or (registration_allowed is not None and not registration_allowed()):
            raise HuggingFaceHubError("FR-HF-DOWNLOAD-CANCELLED")
        return {"transfer": transfer, "model": self._register_verified(destination.resolve(), str(transfer["sha256"]))}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
