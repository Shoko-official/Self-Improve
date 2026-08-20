"""Generate a deterministic CycloneDX inventory from committed dependency locks."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import subprocess
import tomllib
from pathlib import Path
from urllib.parse import quote


def _hash(path: Path) -> str:
    normalized = path.read_text(encoding="utf-8").replace("\r\n", "\n").encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


def _component(component_type: str, group: str, name: str, version: str, ecosystem: str, license_expression: str | None = None, hashes: list[dict[str, str]] | None = None) -> dict[str, object]:
    namespace = f"{quote(group, safe='')}/" if group else ""
    bom_ref = f"pkg:{ecosystem}/{namespace}{quote(name, safe='')}@{quote(version, safe='')}"
    component: dict[str, object] = {"type": component_type, "bom-ref": bom_ref, "group": group, "name": name, "version": version, "purl": bom_ref}
    if license_expression:
        component["licenses"] = [{"expression": license_expression}]
    if hashes:
        component["hashes"] = hashes
    return component


def _node_license_map(root: Path) -> dict[tuple[str, str], str]:
    result: dict[tuple[str, str], str] = {}
    store = root / "node_modules" / ".pnpm"
    if not store.is_dir():
        return result
    for path in store.glob("*/node_modules/*/package.json"):
        try:
            package = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(package.get("name"), str) and isinstance(package.get("version"), str) and isinstance(package.get("license"), str):
            result[(package["name"], package["version"])] = package["license"]
    for path in store.glob("*/node_modules/@*/*/package.json"):
        try:
            package = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(package.get("name"), str) and isinstance(package.get("version"), str) and isinstance(package.get("license"), str):
            result[(package["name"], package["version"])] = package["license"]
    return result


def pnpm_components(root: Path) -> list[dict[str, object]]:
    lines = (root / "pnpm-lock.yaml").read_text(encoding="utf-8").splitlines()
    licenses = _node_license_map(root)
    components: list[dict[str, object]] = []
    in_packages = False
    pending: tuple[str, str, str] | None = None
    for line in lines:
        if line == "packages:":
            in_packages = True
            continue
        if in_packages and line and not line.startswith(" "):
            break
        if not in_packages:
            continue
        match = re.fullmatch(r"  (.+):", line)
        if match:
            key = match.group(1).strip("'").split("(", 1)[0]
            if "@" not in key:
                pending = None
                continue
            name, version = key.rsplit("@", 1)
            group, short_name = (name[1:].split("/", 1) if name.startswith("@") else ("", name))
            pending = (name, group, short_name)
            components.append(_component("library", group, short_name, version, "npm", licenses.get((name, version))))
            continue
        integrity = re.search(r"integrity: (sha512|sha256)-([^,}]+)", line)
        if pending and integrity and components:
            try:
                content = base64.b64decode(integrity.group(2)).hex()
            except ValueError:
                continue
            components[-1]["hashes"] = [{"alg": integrity.group(1).upper().replace("SHA", "SHA-"), "content": content}]
    return components


def cargo_components(root: Path) -> list[dict[str, object]]:
    lock = tomllib.loads((root / "src-tauri" / "Cargo.lock").read_text(encoding="utf-8"))
    metadata = subprocess.run(
        ["cargo", "metadata", "--manifest-path", str(root / "src-tauri" / "Cargo.toml"), "--format-version", "1", "--locked"],
        capture_output=True, text=True, encoding="utf-8", check=True,
    )
    licenses = {(package["name"], package["version"]): package.get("license") for package in json.loads(metadata.stdout)["packages"]}
    components = []
    for package in lock["package"]:
        hashes = [{"alg": "SHA-256", "content": package["checksum"]}] if package.get("checksum") else None
        components.append(_component("library", "", package["name"], package["version"], "cargo", licenses.get((package["name"], package["version"])), hashes))
    return components


def python_build_components(root: Path) -> list[dict[str, object]]:
    components = []
    for raw in (root / "requirements-build.txt").read_text(encoding="utf-8").splitlines():
        requirement = raw.split(";", 1)[0].strip()
        if not requirement or "==" not in requirement:
            continue
        name, version = requirement.split("==", 1)
        components.append(_component("library", "", name, version, "pypi"))
    return components


def create_sbom(root: Path) -> dict[str, object]:
    components = pnpm_components(root) + cargo_components(root) + python_build_components(root)
    unique = {component["bom-ref"]: component for component in components}
    properties = []
    for relative in ("pnpm-lock.yaml", "src-tauri/Cargo.lock", "requirements-build.txt"):
        properties.append({"name": f"shoko:lock-sha256:{relative}", "value": _hash(root / relative)})
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "version": 1,
        "metadata": {
            "component": {"type": "application", "bom-ref": "pkg:generic/shokos-llm@0.1.0", "name": "Shoko's LLM", "version": "0.1.0"},
            "properties": properties,
        },
        "components": [unique[key] for key in sorted(unique)],
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="generate-sbom")
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output or root / "SBOM.cdx.json"
    result = create_sbom(root)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"components": len(result["components"]), "output": str(output), "sha256": _hash(output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
