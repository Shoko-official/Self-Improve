"""Development control CLI for the local Frontier engine."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import threading
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from frontier_engine.__main__ import doctor
from frontier_engine.claims import ClaimLedger
from frontier_engine.literature import LiteratureStore
from frontier_engine.loopback import LoopbackService
from frontier_engine.environments import list_manifests, probe_environment
from frontier_engine.store import FrontierStore


def data_root() -> Path:
    configured = os.environ.get("FRONTIER_DATA_DIR")
    return Path(configured) if configured else Path.home() / ".frontier-data"


def status(root: Path) -> dict[str, object]:
    store = FrontierStore(root)
    try:
        counts = {table: store.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in ("projects", "sessions", "artifacts", "artifact_versions", "jobs")}
    finally:
        store.close()
    return {"data_root": str(root), "counts": counts}


def projects(root: Path) -> dict[str, object]:
    store = FrontierStore(root)
    try:
        records = [dict(row) for row in store.connection.execute("SELECT id, name, instructions, archived_at, created_at FROM projects ORDER BY created_at, id")]
    finally:
        store.close()
    return {"projects": records}


def create_project(root: Path, name: str) -> dict[str, object]:
    name = name.strip()
    if not name:
        raise ValueError("Project name is required.")
    store = FrontierStore(root)
    try:
        project_id = store.create_project(name)
    finally:
        store.close()
    return {"id": project_id, "name": name}


def sessions(root: Path, project_id: str) -> dict[str, object]:
    store = FrontierStore(root)
    try:
        records = [dict(row) for row in store.connection.execute("SELECT id, project_id, title, parent_session_id, reasoning_effort, starred, created_at FROM sessions WHERE project_id = ? ORDER BY created_at, id", (project_id,))]
    finally:
        store.close()
    return {"project_id": project_id, "sessions": records}


def create_session(root: Path, project_id: str, title: str, parent_session_id: str | None = None) -> dict[str, object]:
    title = title.strip()
    if not title:
        raise ValueError("Session title is required.")
    store = FrontierStore(root)
    try:
        session_id = store.create_session(project_id, title, parent_session_id=parent_session_id)
    finally:
        store.close()
    return {"id": session_id, "project_id": project_id, "title": title, "parent_session_id": parent_session_id}


def set_session_starred(root: Path, session_id: str, starred: bool) -> dict[str, object]:
    store = FrontierStore(root)
    try:
        store.set_session_starred(session_id, starred)
    finally:
        store.close()
    return {"id": session_id, "starred": starred}


def archive_project(root: Path, project_id: str) -> dict[str, object]:
    store = FrontierStore(root)
    try:
        store.archive_project(project_id)
    finally:
        store.close()
    return {"id": project_id, "archived": True}


def jobs(root: Path) -> dict[str, object]:
    store = FrontierStore(root)
    try:
        records = [dict(row) for row in store.connection.execute("SELECT id, project_id, session_id, operation, state, created_at, started_at, completed_at FROM jobs ORDER BY created_at DESC, id DESC")]
    finally:
        store.close()
    return {"jobs": records}


def enqueue_job(root: Path, project_id: str, operation: str) -> dict[str, object]:
    store = FrontierStore(root)
    try:
        job_id = store.create_job(project_id, operation, {})
    finally:
        store.close()
    return {"id": job_id, "project_id": project_id, "operation": operation, "state": "queued"}


def cancel_job(root: Path, job_id: str) -> dict[str, object]:
    store = FrontierStore(root)
    try:
        job = store.request_cancellation(job_id)
    finally:
        store.close()
    return job


def artifacts(root: Path, project_id: str) -> dict[str, object]:
    store = FrontierStore(root)
    try:
        records = [dict(row) for row in store.connection.execute("SELECT id, name, media_type, session_id, created_at FROM artifacts WHERE project_id = ? ORDER BY created_at, id", (project_id,))]
    finally:
        store.close()
    return {"project_id": project_id, "artifacts": records}


def create_artifact(root: Path, project_id: str, name: str, media_type: str, content: str) -> dict[str, object]:
    name = name.strip()
    if not name or not media_type:
        raise ValueError("Artifact name and media type are required.")
    store = FrontierStore(root)
    try:
        artifact_id = store.create_artifact(project_id, name, media_type)
        version = store.add_artifact_version(artifact_id, content.encode(), messages={"source": "frontierctl"}, execution_log={"state": "not_executed"})
    finally:
        store.close()
    return {"id": artifact_id, "name": name, "version": version}


def artifact_versions(root: Path, artifact_id: str) -> dict[str, object]:
    store = FrontierStore(root)
    try:
        versions = store.artifact_versions(artifact_id)
    finally:
        store.close()
    return {"artifact_id": artifact_id, "versions": versions}


def literature_queries(root: Path) -> dict[str, object]:
    store = LiteratureStore(root / "literature.sqlite3")
    try: return {"queries": store.queries()}
    finally: store.close()


def record_literature_query(root: Path, query: str, source: str, result_count: int) -> dict[str, object]:
    store = LiteratureStore(root / "literature.sqlite3")
    try: query_id = store.record_query(query, source, "{}", result_count)
    finally: store.close()
    return {"id": query_id, "query": query, "source": source, "result_count": result_count}


def claims(root: Path) -> dict[str, object]:
    ledger = ClaimLedger(root / "claims.sqlite3")
    try: return {"claims": ledger.list()}
    finally: ledger.close()


def create_claim(root: Path, claim_type: str, text: str, uncertainty: str, evidence: list[tuple[str, str]]) -> dict[str, object]:
    ledger = ClaimLedger(root / "claims.sqlite3")
    try: claim_id = ledger.create(claim_type, text, uncertainty, evidence)
    finally: ledger.close()
    return {"id": claim_id, "claim_type": claim_type, "text": text, "uncertainty": uncertainty, "evidence": evidence}


def set_claim_status(root: Path, claim_id: str, status: str) -> dict[str, object]:
    ledger = ClaimLedger(root / "claims.sqlite3")
    try: ledger.set_status(claim_id, status)
    finally: ledger.close()
    return {"id": claim_id, "status": status}


def export_data(root: Path, output: Path) -> dict[str, object]:
    root = root.resolve()
    output = output.resolve()
    if output.exists():
        raise FileExistsError(f"Export destination already exists: {output}")
    if output.is_relative_to(root):
        raise ValueError("Export destination must be outside the Frontier data root.")
    store = FrontierStore(root)
    store.close()
    files = [path for path in sorted(root.rglob("*")) if path.is_file()]
    manifest_files = [
        {"path": path.relative_to(root).as_posix(), "sha256": _sha256(path), "size": path.stat().st_size}
        for path in files
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "x", compression=ZIP_DEFLATED) as archive:
        archive.writestr("frontier-export.json", json.dumps({"protocol_version": 1, "files": manifest_files}, sort_keys=True))
        for path in files:
            archive.write(path, path.relative_to(root).as_posix())
    return {"archive": str(output), "files": len(files), "data_root": str(root)}


def import_data(archive_path: Path, destination: Path) -> dict[str, object]:
    archive_path = archive_path.resolve()
    destination = destination.resolve()
    if not archive_path.is_file():
        raise FileNotFoundError(f"Import archive not found: {archive_path}")
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Import destination must be empty.")
    destination.mkdir(parents=True, exist_ok=True)
    with ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise ValueError("Import archive has an invalid member checksum.")
        members = {member.filename: member for member in archive.infolist() if not member.is_dir()}
        _validate_archive_paths(members)
        manifest = json.loads(archive.read("frontier-export.json"))
        if manifest.get("protocol_version") != 1 or not isinstance(manifest.get("files"), list):
            raise ValueError("Import archive has an unsupported manifest.")
        expected = {entry["path"]: entry for entry in manifest["files"]}
        if set(members) != {"frontier-export.json", *expected}:
            raise ValueError("Import archive members do not match its manifest.")
        for relative_path, entry in expected.items():
            payload = archive.read(relative_path)
            if len(payload) != entry["size"] or hashlib.sha256(payload).hexdigest() != entry["sha256"]:
                raise ValueError(f"Import archive integrity check failed: {relative_path}")
            target = destination / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
    return {"archive": str(archive_path), "files": len(expected), "data_root": str(destination)}


def _validate_archive_paths(members: dict[str, object]) -> None:
    if "frontier-export.json" not in members:
        raise ValueError("Import archive is missing its manifest.")
    for name in members:
        path = Path(name)
        if path.is_absolute() or ".." in path.parts or name != path.as_posix():
            raise ValueError(f"Import archive has an unsafe path: {name}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(prog="frontierctl")
    parser.add_argument("command", choices=("doctor", "status", "config", "serve", "environments", "projects", "sessions", "star-session", "archive-project", "jobs", "cancel-job", "artifacts", "artifact-versions", "literature", "claims", "set-claim-status", "export", "import"))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--name")
    parser.add_argument("--project-id")
    parser.add_argument("--session-id")
    parser.add_argument("--title")
    parser.add_argument("--parent-session-id")
    parser.add_argument("--starred", choices=("true", "false"))
    parser.add_argument("--operation")
    parser.add_argument("--job-id")
    parser.add_argument("--artifact-id")
    parser.add_argument("--media-type")
    parser.add_argument("--content", default="")
    parser.add_argument("--query")
    parser.add_argument("--source")
    parser.add_argument("--result-count", type=int)
    parser.add_argument("--claim-id")
    parser.add_argument("--claim-type", choices=("source", "observation", "computed", "inference", "hypothesis"))
    parser.add_argument("--claim-text")
    parser.add_argument("--uncertainty")
    parser.add_argument("--claim-status", choices=("draft", "supported", "disputed", "retracted"))
    parser.add_argument("--evidence", action="append", nargs=2, metavar=("URI", "SELECTOR"))
    parser.add_argument("--language", choices=("python", "r"))
    parser.add_argument("--duration-seconds", type=float)
    args = parser.parse_args()
    root = data_root()
    if args.command == "doctor":
        result = doctor()
    elif args.command == "status":
        result = status(root)
    elif args.command == "config":
        result = {"data_root": str(root), "environment_variable": "FRONTIER_DATA_DIR"}
    elif args.command == "serve":
        if args.duration_seconds is not None and args.duration_seconds < 0:
            parser.error("serve --duration-seconds must be non-negative")
        service = LoopbackService()
        service.start()
        result = {"url": service.url, "status_path": "/status", "authorization": "Bearer", "token": service.token}
        print(json.dumps(result, sort_keys=True) if args.json else json.dumps(result, indent=2, sort_keys=True))
        try:
            threading.Event().wait(args.duration_seconds)
        except KeyboardInterrupt:
            pass
        finally:
            service.close()
        return
    elif args.command == "environments":
        result = {"manifests": list_manifests(root), "probe": probe_environment(args.language or "python")}
    elif args.command == "projects":
        result = create_project(root, args.name) if args.name is not None else projects(root)
    elif args.command == "sessions":
        if args.project_id is None:
            parser.error("sessions requires --project-id")
        result = create_session(root, args.project_id, args.title, args.parent_session_id) if args.title is not None else sessions(root, args.project_id)
    elif args.command == "star-session":
        if args.session_id is None or args.starred is None:
            parser.error("star-session requires --session-id and --starred true|false")
        result = set_session_starred(root, args.session_id, args.starred == "true")
    elif args.command == "archive-project":
        if args.project_id is None:
            parser.error("archive-project requires --project-id")
        result = archive_project(root, args.project_id)
    elif args.command == "jobs":
        if args.project_id is None or args.operation is None:
            result = jobs(root)
        else:
            result = enqueue_job(root, args.project_id, args.operation)
    elif args.command == "cancel-job":
        if args.job_id is None:
            parser.error("cancel-job requires --job-id")
        result = cancel_job(root, args.job_id)
    elif args.command == "artifacts":
        if args.project_id is None:
            parser.error("artifacts requires --project-id")
        result = create_artifact(root, args.project_id, args.name, args.media_type, args.content) if args.name is not None and args.media_type is not None else artifacts(root, args.project_id)
    elif args.command == "artifact-versions":
        if args.artifact_id is None:
            parser.error("artifact-versions requires --artifact-id")
        result = artifact_versions(root, args.artifact_id)
    elif args.command == "literature":
        if args.query is None:
            result = literature_queries(root)
        elif args.source is None or args.result_count is None:
            parser.error("literature query requires --source and --result-count")
        else:
            result = record_literature_query(root, args.query, args.source, args.result_count)
    elif args.command == "claims":
        if args.claim_type is None and args.claim_text is None and args.uncertainty is None and args.evidence is None:
            result = claims(root)
        elif args.claim_type is None or args.claim_text is None or args.uncertainty is None:
            parser.error("claims create requires --claim-type, --claim-text, and --uncertainty")
        else:
            result = create_claim(root, args.claim_type, args.claim_text, args.uncertainty, args.evidence or [])
    elif args.command == "set-claim-status":
        if args.claim_id is None or args.claim_status is None:
            parser.error("set-claim-status requires --claim-id and --claim-status")
        result = set_claim_status(root, args.claim_id, args.claim_status)
    elif args.command == "export":
        if args.output is None:
            parser.error("export requires --output PATH")
        result = export_data(root, args.output)
    else:
        if args.input is None or args.destination is None:
            parser.error("import requires --input PATH and --destination PATH")
        result = import_data(args.input, args.destination)
    print(json.dumps(result, sort_keys=True) if args.json else json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
