"""Development control CLI for the local Frontier engine."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from frontier_engine.__main__ import doctor
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
    parser.add_argument("command", choices=("doctor", "status", "config", "export", "import"))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--destination", type=Path)
    args = parser.parse_args()
    root = data_root()
    if args.command == "doctor":
        result = doctor()
    elif args.command == "status":
        result = status(root)
    elif args.command == "config":
        result = {"data_root": str(root), "environment_variable": "FRONTIER_DATA_DIR"}
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
