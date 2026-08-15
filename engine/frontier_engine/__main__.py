"""Small, dependency-free capability probe used before runtime packs are installed."""

from __future__ import annotations

import argparse
import json
import os
import platform
from datetime import UTC, datetime


def doctor() -> dict[str, object]:
    return {
        "protocol_version": 1,
        "status": "healthy",
        "host": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "logical_cores": os.cpu_count() or 1,
        },
        "checked_at": datetime.now(UTC).isoformat(),
        "limits": [
            "No inference runtime pack is installed.",
            "No remote provider is configured.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(prog="frontier-engine")
    parser.add_argument("command", choices=("doctor",))
    args = parser.parse_args()
    if args.command == "doctor":
        print(json.dumps(doctor(), sort_keys=True))


if __name__ == "__main__":
    main()
