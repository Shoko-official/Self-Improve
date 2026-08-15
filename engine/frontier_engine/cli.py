"""Development control CLI for the local Frontier engine."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

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


def main() -> None:
    parser = argparse.ArgumentParser(prog="frontierctl")
    parser.add_argument("command", choices=("doctor", "status", "config"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = data_root()
    result = doctor() if args.command == "doctor" else status(root) if args.command == "status" else {"data_root": str(root), "environment_variable": "FRONTIER_DATA_DIR"}
    print(json.dumps(result, sort_keys=True) if args.json else json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
