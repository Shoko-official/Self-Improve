"""Validated host integrations without secret disclosure or capability guessing."""

from __future__ import annotations

import hashlib
import json
import os
import queue
import re
import shutil
import sqlite3
import subprocess
import threading
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


MAX_SKILL_BYTES = 256 * 1024
MAX_SELECTED_SKILLS = 4
MAX_SELECTED_SKILL_BYTES = 512 * 1024
MAX_MCP_BYTES = 1024 * 1024
MAX_DISCOVERED_FILES = 2_000
MCP_PROTOCOL_VERSION = "2025-06-18"
_FRONTMATTER = re.compile(r"\A---\s*\r?\n(.*?)\r?\n---\s*\r?\n", re.DOTALL)


def discover_skills(
    skill_roots: list[tuple[str, Path]] | None = None,
    config_path: Path | None = None,
    plugin_root: Path | None = None,
) -> list[dict[str, object]]:
    records = _skill_records(skill_roots, config_path, plugin_root)
    return [{key: value for key, value in record.items() if not key.startswith("_")} for record in records]


def load_skill_instructions(
    skill_id: str,
    skill_roots: list[tuple[str, Path]] | None = None,
    config_path: Path | None = None,
    plugin_root: Path | None = None,
) -> dict[str, str]:
    record = next((item for item in _skill_records(skill_roots, config_path, plugin_root) if item["id"] == skill_id), None)
    if record is None:
        raise KeyError("FR-SKILL-NOT-AVAILABLE")
    path = Path(str(record["_path"]))
    content = path.read_text(encoding="utf-8")
    if len(content.encode("utf-8")) > MAX_SKILL_BYTES:
        raise ValueError("FR-SKILL-SIZE")
    return {"id": str(record["id"]), "name": str(record["name"]), "instructions": content, "sha256": str(record["sha256"])}


def apply_skill_instructions(prompt: str, skill_ids: list[str]) -> tuple[str, list[dict[str, str]]]:
    selected = []
    seen = set()
    for skill_id in skill_ids:
        if skill_id in seen:
            continue
        if len(selected) >= MAX_SELECTED_SKILLS:
            raise ValueError("FR-SKILL-SELECTION-LIMIT")
        selected.append(load_skill_instructions(skill_id))
        seen.add(skill_id)
    if not selected:
        return prompt, []
    if sum(len(skill["instructions"].encode("utf-8")) for skill in selected) > MAX_SELECTED_SKILL_BYTES:
        raise ValueError("FR-SKILL-SELECTION-SIZE")
    instruction_blocks = "\n\n".join(
        f"<skill id={json.dumps(skill['id'])} sha256={json.dumps(skill['sha256'])}>\n{skill['instructions']}\n</skill>"
        for skill in selected
    )
    compiled = (
        "Apply the user-selected skill instructions below. Treat referenced files and tools as unavailable unless they are separately provided by the runtime. "
        "Never claim that an unavailable tool was used.\n\n"
        f"{instruction_blocks}\n\n<user_request>\n{prompt}\n</user_request>"
    )
    return compiled, [{"id": item["id"], "name": item["name"], "sha256": item["sha256"]} for item in selected]


def discover_extensions(config_path: Path | None = None, plugin_root: Path | None = None) -> list[dict[str, object]]:
    skill_ids = {str(item["id"]) for item in discover_skills(config_path=config_path, plugin_root=plugin_root)}
    extensions = []
    for plugin in _enabled_plugins(config_path, plugin_root):
        contributed = sorted(identifier for identifier in skill_ids if identifier.startswith(f"plugin/{plugin['id']}/"))
        if not contributed:
            continue
        extensions.append({
            "id": plugin["id"],
            "name": plugin["name"],
            "version": plugin["version"],
            "license": plugin["license"],
            "capabilities": ["skill.instructions"],
            "skill_ids": contributed,
            "network": "inherits-run-policy",
            "availability": "installed-and-loadable",
        })
    return extensions


def probe_mcp_servers(
    approved: bool,
    config_path: Path | None = None,
    plugin_root: Path | None = None,
) -> dict[str, object]:
    candidates = _mcp_candidates(config_path, plugin_root)
    if candidates and not approved:
        raise PermissionError("FR-MCP-APPROVAL: probing configured servers may start processes or access the network")
    verified = []
    failures = []
    for candidate in candidates:
        try:
            result = _mcp_exchange(candidate, "tools/list", {})
            tools = _safe_tools(result.get("tools"))
            verified.append({
                "id": candidate["id"],
                "capabilities": [str(tool["name"]) for tool in tools],
                "network": "explicit-egress-or-process",
                "availability": "verified",
                "transport": candidate["transport"],
                "tools": tools,
                "verified_at": _now(),
            })
        except Exception as error:
            failures.append({"id": candidate["id"], "code": _diagnostic_code(error)})
    return {"connectors": verified, "failures": failures, "detected": len(candidates)}


def call_mcp_tool(
    server_id: str,
    tool_name: str,
    arguments: Mapping[str, object],
    approved: bool,
    config_path: Path | None = None,
    plugin_root: Path | None = None,
) -> dict[str, object]:
    if not approved:
        raise PermissionError("FR-MCP-APPROVAL: each MCP tool call requires explicit approval")
    candidate = next((item for item in _mcp_candidates(config_path, plugin_root) if item["id"] == server_id), None)
    if candidate is None:
        raise KeyError("FR-MCP-NOT-CONFIGURED")
    listed = _safe_tools(_mcp_exchange(candidate, "tools/list", {}).get("tools"))
    if tool_name not in {str(tool["name"]) for tool in listed}:
        raise ValueError("FR-MCP-TOOL-NOT-AVAILABLE")
    result = _mcp_exchange(candidate, "tools/call", {"name": tool_name, "arguments": dict(arguments)})
    encoded = json.dumps(result, sort_keys=True).encode("utf-8")
    if len(encoded) > MAX_MCP_BYTES:
        raise ValueError("FR-MCP-RESPONSE-SIZE")
    return {"server_id": server_id, "tool_name": tool_name, "result": result, "completed_at": _now()}


class IntegrationLedger:
    def __init__(self, database: Path) -> None:
        database.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(database)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS integration_events (id TEXT PRIMARY KEY,project_id TEXT,integration_id TEXT NOT NULL,action TEXT NOT NULL,state TEXT NOT NULL,diagnostic_code TEXT,created_at TEXT NOT NULL)"
        )
        self.connection.commit()

    def record(self, integration_id: str, action: str, state: str, diagnostic_code: str | None = None, project_id: str | None = None) -> None:
        self.connection.execute(
            "INSERT INTO integration_events VALUES(?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), project_id, integration_id, action, state, diagnostic_code, _now()),
        )
        self.connection.commit()

    def events(self, project_id: str | None = None) -> list[dict[str, object]]:
        where = "WHERE project_id=?" if project_id else ""
        parameters: tuple[str, ...] = (project_id,) if project_id else ()
        return [dict(row) for row in self.connection.execute(f"SELECT * FROM integration_events {where} ORDER BY created_at DESC,id DESC", parameters)]

    def close(self) -> None:
        self.connection.close()


def _skill_records(
    skill_roots: list[tuple[str, Path]] | None,
    config_path: Path | None,
    plugin_root: Path | None,
) -> list[dict[str, object]]:
    roots = skill_roots or _default_skill_roots(config_path)
    roots = list(roots)
    for plugin in _enabled_plugins(config_path, plugin_root):
        skills_path = plugin.get("_skills_path")
        if isinstance(skills_path, Path):
            roots.append((f"plugin/{plugin['id']}", skills_path))
    records = []
    identifiers = set()
    scanned = 0
    for source, root in roots:
        if not root.is_dir():
            continue
        resolved_root = root.resolve()
        for path in sorted(root.rglob("SKILL.md")):
            scanned += 1
            if scanned > MAX_DISCOVERED_FILES:
                raise ValueError("FR-SKILL-DISCOVERY-LIMIT")
            try:
                resolved = path.resolve(strict=True)
                resolved.relative_to(resolved_root)
                size = resolved.stat().st_size
                if size <= 0 or size > MAX_SKILL_BYTES:
                    continue
                content = resolved.read_text(encoding="utf-8")
                metadata = _skill_metadata(content)
            except (OSError, UnicodeError, ValueError):
                continue
            relative = resolved.parent.relative_to(resolved_root).as_posix()
            identifier = f"{source}/{relative}".rstrip("/")
            if identifier in identifiers:
                continue
            identifiers.add(identifier)
            records.append({
                "id": identifier,
                "name": metadata["name"],
                "description": metadata["description"],
                "capabilities": ["prompt.instructions"],
                "network": "inherits-run-policy",
                "availability": "validated-manifest",
                "source": source,
                "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                "_path": str(resolved),
            })
    return sorted(records, key=lambda item: (str(item["source"]), str(item["name"]), str(item["id"])))


def _skill_metadata(content: str) -> dict[str, str]:
    matched = _FRONTMATTER.match(content)
    if matched is None:
        raise ValueError("FR-SKILL-FRONTMATTER")
    values = {}
    for line in matched.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        if key in {"name", "description"}:
            values[key] = value.strip().strip("'\"")
    name = values.get("name", "").strip().replace("\u2014", "-").replace("\u2013", "-")
    description = values.get("description", "").strip().replace("\u2014", "-").replace("\u2013", "-")
    if not name or not description or len(name) > 128 or len(description) > 2_000:
        raise ValueError("FR-SKILL-METADATA")
    return {"name": name, "description": description}


def _default_skill_roots(config_path: Path | None) -> list[tuple[str, Path]]:
    override = os.environ.get("SHOKO_SKILLS_ROOTS")
    if override:
        return [(f"explicit-{index + 1}", Path(value)) for index, value in enumerate(override.split(os.pathsep)) if value]
    home = (config_path.parent if config_path else _codex_home())
    return [("codex", home / "skills"), ("agents", Path.home() / ".agents" / "skills")]


def _enabled_plugins(config_path: Path | None, plugin_root: Path | None) -> list[dict[str, object]]:
    config = _load_codex_config(config_path)
    enabled = {str(identifier) for identifier, item in dict(config.get("plugins") or {}).items() if isinstance(item, Mapping) and item.get("enabled") is True}
    root = plugin_root or _codex_home(config_path) / "plugins" / "cache"
    if not enabled or not root.is_dir():
        return []
    plugins = []
    count = 0
    for manifest_path in sorted(root.rglob("plugin.json")):
        count += 1
        if count > MAX_DISCOVERED_FILES:
            raise ValueError("FR-PLUGIN-DISCOVERY-LIMIT")
        if manifest_path.parent.name != ".codex-plugin":
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            plugin_directory = manifest_path.parent.parent.resolve(strict=True)
            relative = plugin_directory.relative_to(root.resolve())
            marketplace = relative.parts[0]
            name = str(manifest["name"])
            identifier = f"{name}@{marketplace}"
            if identifier not in enabled:
                continue
            skills_path = _plugin_child(plugin_directory, manifest.get("skills"))
            mcp_path = _plugin_child(plugin_directory, manifest.get("mcpServers"))
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            continue
        plugins.append({
            "id": identifier,
            "name": name,
            "version": str(manifest.get("version") or "unknown"),
            "license": str(manifest.get("license") or "unspecified"),
            "_skills_path": skills_path if skills_path and skills_path.is_dir() else None,
            "_mcp_path": mcp_path if mcp_path and mcp_path.is_file() else None,
        })
    newest = {}
    for plugin in plugins:
        existing = newest.get(plugin["id"])
        if existing is None or _natural_key(str(plugin["version"])) > _natural_key(str(existing["version"])):
            newest[plugin["id"]] = plugin
    return [newest[key] for key in sorted(newest)]


def _plugin_child(root: Path, raw: object) -> Path | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    child = (root / raw).resolve()
    try:
        child.relative_to(root)
    except ValueError:
        return None
    return child


def _mcp_candidates(config_path: Path | None, plugin_root: Path | None) -> list[dict[str, object]]:
    config = _load_codex_config(config_path)
    candidates = []
    for name, raw in dict(config.get("mcp_servers") or {}).items():
        if isinstance(raw, Mapping):
            candidate = _normalize_mcp_candidate(f"codex/{name}", raw)
            if candidate:
                candidates.append(candidate)
    for plugin in _enabled_plugins(config_path, plugin_root):
        mcp_path = plugin.get("_mcp_path")
        if not isinstance(mcp_path, Path):
            continue
        try:
            payload = json.loads(mcp_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for name, raw in dict(payload.get("mcpServers") or {}).items():
            if isinstance(raw, Mapping):
                candidate = _normalize_mcp_candidate(f"plugin/{plugin['id']}/{name}", raw)
                if candidate:
                    candidates.append(candidate)
    deduplicated = {}
    for candidate in candidates:
        deduplicated[str(candidate["id"])] = candidate
    return [deduplicated[key] for key in sorted(deduplicated)]


def _normalize_mcp_candidate(identifier: str, raw: Mapping[str, object]) -> dict[str, object] | None:
    if raw.get("enabled") is False or raw.get("disabled") is True:
        return None
    url = raw.get("url")
    if isinstance(url, str):
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in {"http", "https"} or parsed.hostname is None or parsed.username or parsed.password:
            return None
        return {
            "id": identifier,
            "transport": "http",
            "url": url,
            "headers": dict(raw.get("http_headers") or raw.get("headers") or {}),
            "env_headers": dict(raw.get("env_http_headers") or {}),
            "bearer_token_env_var": raw.get("bearer_token_env_var"),
            "timeout": _bounded_timeout(raw.get("tool_timeout_sec") or raw.get("timeout_sec")),
        }
    command = raw.get("command")
    args = raw.get("args") or []
    environment = raw.get("env") or {}
    if not isinstance(command, str) or not command.strip() or not isinstance(args, list) or not all(isinstance(item, str) for item in args):
        return None
    if not isinstance(environment, Mapping) or not all(isinstance(key, str) and isinstance(value, str) for key, value in environment.items()):
        return None
    return {
        "id": identifier,
        "transport": "stdio",
        "command": command,
        "args": list(args),
        "env": dict(environment),
        "cwd": raw.get("cwd"),
        "timeout": _bounded_timeout(raw.get("startup_timeout_sec") or raw.get("tool_timeout_sec")),
    }


def _mcp_exchange(candidate: Mapping[str, object], method: str, params: Mapping[str, object]) -> dict[str, Any]:
    return _stdio_exchange(candidate, method, params) if candidate["transport"] == "stdio" else _http_exchange(candidate, method, params)


def _stdio_exchange(candidate: Mapping[str, object], method: str, params: Mapping[str, object]) -> dict[str, Any]:
    command = str(candidate["command"])
    executable = command if Path(command).is_absolute() and Path(command).is_file() else shutil.which(command)
    if executable is None:
        raise RuntimeError("FR-MCP-COMMAND-NOT-FOUND")
    cwd = candidate.get("cwd")
    if cwd is not None and (not isinstance(cwd, str) or not Path(cwd).is_dir()):
        raise RuntimeError("FR-MCP-CWD")
    environment = {**os.environ, **dict(candidate.get("env") or {})}
    options: dict[str, object] = {
        "stdin": subprocess.PIPE,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.DEVNULL,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "env": environment,
        "cwd": cwd,
    }
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW
    process = subprocess.Popen([executable, *list(candidate.get("args") or [])], **options)
    messages: queue.Queue[object] = queue.Queue()

    def read_messages() -> None:
        received = 0
        try:
            assert process.stdout is not None
            for line in process.stdout:
                received += len(line.encode("utf-8", errors="replace"))
                if received > MAX_MCP_BYTES:
                    messages.put(RuntimeError("FR-MCP-RESPONSE-SIZE"))
                    return
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    messages.put(payload)
        finally:
            messages.put(RuntimeError("FR-MCP-PROCESS-EXITED"))

    reader = threading.Thread(target=read_messages, daemon=True)
    reader.start()
    try:
        _write_message(process, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": MCP_PROTOCOL_VERSION, "capabilities": {}, "clientInfo": {"name": "shokos-llm", "version": "0.1.0"}}})
        initialize_result = _wait_message(messages, 1, float(candidate["timeout"]))
        if initialize_result.get("protocolVersion") != MCP_PROTOCOL_VERSION:
            raise RuntimeError("FR-MCP-PROTOCOL-VERSION")
        _write_message(process, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        _write_message(process, {"jsonrpc": "2.0", "id": 2, "method": method, "params": dict(params)})
        return _wait_message(messages, 2, float(candidate["timeout"]))
    finally:
        if process.stdin is not None:
            process.stdin.close()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        reader.join(timeout=1)
        if process.stdout is not None:
            process.stdout.close()


def _write_message(process: subprocess.Popen[str], payload: Mapping[str, object]) -> None:
    if process.stdin is None:
        raise RuntimeError("FR-MCP-STDIN")
    process.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
    process.stdin.flush()


def _wait_message(messages: queue.Queue[object], identifier: int, timeout: float) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("FR-MCP-TIMEOUT")
        try:
            item = messages.get(timeout=remaining)
        except queue.Empty as error:
            raise TimeoutError("FR-MCP-TIMEOUT") from error
        if isinstance(item, Exception):
            raise item
        if not isinstance(item, dict) or item.get("id") != identifier:
            continue
        if "error" in item:
            raise RuntimeError("FR-MCP-REMOTE-ERROR")
        result = item.get("result")
        if not isinstance(result, dict):
            raise RuntimeError("FR-MCP-INVALID-RESULT")
        return result


def _http_exchange(candidate: Mapping[str, object], method: str, params: Mapping[str, object]) -> dict[str, Any]:
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    for key, value in dict(candidate.get("headers") or {}).items():
        if isinstance(key, str) and isinstance(value, str):
            headers[key] = value
    for key, environment_name in dict(candidate.get("env_headers") or {}).items():
        if isinstance(key, str) and isinstance(environment_name, str) and os.environ.get(environment_name):
            headers[key] = os.environ[environment_name]
    bearer_name = candidate.get("bearer_token_env_var")
    if isinstance(bearer_name, str):
        token = os.environ.get(bearer_name)
        if not token:
            raise RuntimeError("FR-MCP-CREDENTIAL-MISSING")
        headers["Authorization"] = f"Bearer {token}"
    initialize, response_headers = _http_post(candidate, headers, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": MCP_PROTOCOL_VERSION, "capabilities": {}, "clientInfo": {"name": "shokos-llm", "version": "0.1.0"}}}, True)
    if "error" in initialize:
        raise RuntimeError("FR-MCP-REMOTE-ERROR")
    initialize_result = initialize.get("result")
    if not isinstance(initialize_result, Mapping) or initialize_result.get("protocolVersion") != MCP_PROTOCOL_VERSION:
        raise RuntimeError("FR-MCP-PROTOCOL-VERSION")
    headers["MCP-Protocol-Version"] = MCP_PROTOCOL_VERSION
    session_id = response_headers.get("Mcp-Session-Id")
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    try:
        _http_post(candidate, headers, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}, False)
        response, _ = _http_post(candidate, headers, {"jsonrpc": "2.0", "id": 2, "method": method, "params": dict(params)}, True)
        if "error" in response:
            raise RuntimeError("FR-MCP-REMOTE-ERROR")
        result = response.get("result")
        if not isinstance(result, dict):
            raise RuntimeError("FR-MCP-INVALID-RESULT")
        return result
    finally:
        if session_id:
            _http_delete(candidate, headers)


def _http_post(candidate: Mapping[str, object], headers: Mapping[str, str], payload: Mapping[str, object], expect_json: bool) -> tuple[dict[str, Any], Mapping[str, str]]:
    request = urllib.request.Request(str(candidate["url"]), data=json.dumps(payload).encode("utf-8"), headers=dict(headers), method="POST")
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=float(candidate["timeout"])) as response:
            body = response.read(MAX_MCP_BYTES + 1)
            if len(body) > MAX_MCP_BYTES:
                raise ValueError("FR-MCP-RESPONSE-SIZE")
            if not expect_json and not body:
                return {}, response.headers
            result = _decode_http_payload(body, response.headers.get("Content-Type", ""))
            return result, response.headers
    except (OSError, urllib.error.URLError, urllib.error.HTTPError) as error:
        raise RuntimeError("FR-MCP-HTTP") from error


def _http_delete(candidate: Mapping[str, object], headers: Mapping[str, str]) -> None:
    request = urllib.request.Request(str(candidate["url"]), headers=dict(headers), method="DELETE")
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=float(candidate["timeout"])):
            return
    except (OSError, urllib.error.URLError, urllib.error.HTTPError):
        return


def _decode_http_payload(body: bytes, content_type: str) -> dict[str, Any]:
    text = body.decode("utf-8")
    if "text/event-stream" in content_type:
        data_lines = [line[5:].strip() for line in text.splitlines() if line.startswith("data:")]
        if not data_lines:
            raise RuntimeError("FR-MCP-SSE")
        text = data_lines[-1]
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise RuntimeError("FR-MCP-INVALID-RESPONSE")
    return payload


def _safe_tools(raw: object) -> list[dict[str, object]]:
    if not isinstance(raw, list):
        raise RuntimeError("FR-MCP-TOOLS")
    tools = []
    for item in raw[:500]:
        if not isinstance(item, Mapping) or not isinstance(item.get("name"), str):
            continue
        tools.append({key: item[key] for key in ("name", "title", "description", "inputSchema", "annotations") if key in item})
    return tools


def _load_codex_config(config_path: Path | None) -> dict[str, object]:
    path = config_path or _codex_home() / "config.toml"
    if not path.is_file():
        return {}
    try:
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _codex_home(config_path: Path | None = None) -> Path:
    if config_path is not None:
        return config_path.parent
    configured = os.environ.get("CODEX_HOME")
    return Path(configured) if configured else Path.home() / ".codex"


def _bounded_timeout(raw: object) -> float:
    try:
        value = float(raw or 8)
    except (TypeError, ValueError):
        value = 8
    return min(30.0, max(1.0, value))


def _natural_key(value: str) -> tuple[tuple[int, object], ...]:
    return tuple((0, int(part)) if part.isdigit() else (1, part.lower()) for part in re.split(r"(\d+)", value))


def _diagnostic_code(error: Exception) -> str:
    text = str(error)
    return text.split(":", 1)[0] if text.startswith("FR-") else "FR-MCP-PROBE"


def _now() -> str:
    return datetime.now(UTC).isoformat()
