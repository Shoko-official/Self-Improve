"""Development control CLI for the local Frontier engine."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import threading
import time
import socket
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from frontier_engine.__main__ import doctor
from frontier_engine.annotations import AnnotationStore
from frontier_engine.agent_state import AgentStateStore
from frontier_engine.agent_runner import run_local_agent
from frontier_engine.automations import AutomationStore, pipeline_capabilities, run_pipeline
from frontier_engine.claims import ClaimLedger
from frontier_engine.literature import LiteratureStore
from frontier_engine.loopback import LoopbackService
from frontier_engine.model_registry import HuggingFaceHub, ModelRegistry
from frontier_engine.model_transfers import MODEL_TRANSFER_OPERATION, create_model_transfer, run_model_transfer
from frontier_engine.environments import create_python_environment, create_r_environment, install_python_packages, install_r_packages, list_manifests, probe_environment
from frontier_engine.generation import run_generation
from frontier_engine.inference import plan_ollama_inference
from frontier_engine.integration_registry import IntegrationLedger, call_mcp_tool, discover_extensions, discover_skills, probe_mcp_servers
from frontier_engine.runtime_install import install_ollama_model as install_local_ollama_model
from frontier_engine.runtimes import stream_ollama, warmup_ollama
from frontier_engine.shell import execute_project_shell
from frontier_engine.store import FrontierStore
from frontier_engine.storage import StorageProfile, build_manifest, execute_local_transfer, execute_s3_signed_transfer
from frontier_engine.s3_signing import S3Credentials
from frontier_engine.scientific_registry import connector_catalog, extension_catalog, skill_catalog
from frontier_engine.compute import ComputePlan, run_remote
from frontier_engine.workspace_tools import ProjectWorkspaceTools
from frontier_engine.reviewer import Claim, review_claims
from frontier_engine.renderers import render_preview
from frontier_engine.managed_runtime import verify_bundle


_BACKGROUND_PROCESSES: dict[int, subprocess.Popen[bytes]] = {}


def data_root() -> Path:
    configured = os.environ.get("FRONTIER_DATA_DIR")
    return Path(configured) if configured else Path.home() / ".frontier-data"


def _control_state_path(root: Path) -> Path: return root / "control-plane-service.json"


def _control_log_path(root: Path) -> Path: return root / "control-plane-service.log"


def _service_alive(pid: int) -> bool:
    if os.name == "nt":
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x00100000, False, pid)
        if not handle: return False
        try: return ctypes.windll.kernel32.WaitForSingleObject(handle, 0) == 0x00000102
        finally: ctypes.windll.kernel32.CloseHandle(handle)
    try: os.kill(pid, 0)
    except ProcessLookupError: return False
    except PermissionError: return True
    return True


def _read_control_state(root: Path) -> dict[str, object] | None:
    path = _control_state_path(root)
    if not path.is_file(): return None
    try: state = json.loads(path.read_text())
    except json.JSONDecodeError: path.unlink(missing_ok=True); return None
    if not isinstance(state, dict) or not isinstance(state.get("pid"), int) or not isinstance(state.get("url"), str):
        path.unlink(missing_ok=True); return None
    if not _service_alive(state["pid"]): path.unlink(missing_ok=True); return None
    return state


def _write_control_state(root: Path, state: dict[str, object]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    path = _control_state_path(root)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, sort_keys=True))
    temporary.replace(path)


def _service_status(root: Path) -> dict[str, object]:
    state = _read_control_state(root)
    return {"running": state is not None, "url": state["url"] if state else None, "pid": state["pid"] if state else None}


def start_background_service(root: Path) -> dict[str, object]:
    if _read_control_state(root) is not None: raise RuntimeError("A Frontier control-plane service is already running.")
    root.mkdir(parents=True, exist_ok=True)
    log_path = _control_log_path(root)
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    command = [sys.executable, "-m", "frontier_engine.cli", "serve", "--background-child", "--data-dir", str(root), "--loopback-port", str(port)]
    environment = {**os.environ, "FRONTIER_DATA_DIR": str(root)}
    options: dict[str, object] = {"cwd": str(Path.cwd()), "env": environment, "stdout": None, "stderr": None, "close_fds": True}
    if os.name == "nt": options["creationflags"] = subprocess.CREATE_NO_WINDOW
    else: options["start_new_session"] = True
    with log_path.open("ab") as log:
        options["stdout"] = log; options["stderr"] = log
        process = subprocess.Popen(command, **options)
    _BACKGROUND_PROCESSES[process.pid] = process
    time.sleep(.05)
    if process.poll() is None:
        _write_control_state(root, {"pid": process.pid, "url": f"http://127.0.0.1:{port}", "started_at": time.time()})
        return _service_status(root)
    detail = log_path.read_text(errors="replace").strip()
    raise RuntimeError(f"The Frontier control-plane service did not start. {detail or 'See frontierctl logs.'}")


def stop_background_service(root: Path) -> dict[str, object]:
    state = _read_control_state(root)
    if state is None: return _service_status(root)
    os.kill(state["pid"], signal.SIGTERM)
    process = _BACKGROUND_PROCESSES.pop(state["pid"], None)
    if process is not None:
        try: process.wait(timeout=5)
        except subprocess.TimeoutExpired: pass
    else:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and _service_alive(state["pid"]): time.sleep(.05)
    if _service_alive(state["pid"]): raise RuntimeError("The Frontier control-plane service did not stop within five seconds.")
    _control_state_path(root).unlink(missing_ok=True)
    return _service_status(root)


def service_logs(root: Path, tail: int) -> dict[str, object]:
    if tail < 0: raise ValueError("Log tail must be non-negative.")
    path = _control_log_path(root)
    lines = path.read_text(errors="replace").splitlines()[-tail:] if path.is_file() else []
    return {"path": str(path), "lines": lines}


def status(root: Path) -> dict[str, object]:
    store = FrontierStore(root)
    try:
        counts = {table: store.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in ("projects", "sessions", "artifacts", "artifact_versions", "jobs")}
    finally:
        store.close()
    return {"data_root": str(root), "counts": counts, "control_service": _service_status(root)}


def projects(root: Path) -> dict[str, object]:
    store = FrontierStore(root)
    try:
        records = [dict(row) for row in store.connection.execute("SELECT id, name, instructions, archived_at, created_at FROM projects ORDER BY created_at, id")]
    finally:
        store.close()
    return {"projects": records}


def create_project(root: Path, name: str, instructions: str = "") -> dict[str, object]:
    name = name.strip()
    if not name:
        raise ValueError("Project name is required.")
    store = FrontierStore(root)
    try:
        project_id = store.create_project(name, instructions)
    finally:
        store.close()
    return {"id": project_id, "name": name, "instructions": instructions}


def set_project_instructions(root: Path, project_id: str, instructions: str) -> dict[str, object]:
    store = FrontierStore(root)
    try: store.set_project_instructions(project_id, instructions)
    finally: store.close()
    return {"id": project_id, "instructions": instructions}


def sessions(root: Path, project_id: str) -> dict[str, object]:
    store = FrontierStore(root)
    try:
        records = [dict(row) for row in store.connection.execute("SELECT id, project_id, title, parent_session_id, reasoning_effort, starred, created_at FROM sessions WHERE project_id = ? ORDER BY created_at, id", (project_id,))]
    finally:
        store.close()
    return {"project_id": project_id, "sessions": records}


def create_session(root: Path, project_id: str, title: str, parent_session_id: str | None = None, reasoning_effort: str = "standard") -> dict[str, object]:
    title = title.strip()
    if not title:
        raise ValueError("Session title is required.")
    store = FrontierStore(root)
    try:
        session_id = store.create_session(project_id, title, reasoning_effort, parent_session_id)
    finally:
        store.close()
    return {"id": session_id, "project_id": project_id, "title": title, "reasoning_effort": reasoning_effort, "parent_session_id": parent_session_id}


def set_session_starred(root: Path, session_id: str, starred: bool) -> dict[str, object]:
    store = FrontierStore(root)
    try:
        store.set_session_starred(session_id, starred)
    finally:
        store.close()
    return {"id": session_id, "starred": starred}


def set_session_reasoning_effort(root: Path, session_id: str, reasoning_effort: str) -> dict[str, object]:
    store = FrontierStore(root)
    try: store.set_session_reasoning_effort(session_id, reasoning_effort)
    finally: store.close()
    return {"id": session_id, "reasoning_effort": reasoning_effort}


def search_sessions(root: Path, query: str, project_id: str | None = None) -> dict[str, object]:
    store = FrontierStore(root)
    try: records = store.search_sessions(query, project_id)
    finally: store.close()
    return {"query": query, "project_id": project_id, "sessions": records}


def archive_project(root: Path, project_id: str) -> dict[str, object]:
    store = FrontierStore(root)
    try:
        store.archive_project(project_id)
    finally:
        store.close()
    return {"id": project_id, "archived": True}


def project_folders(root: Path, project_id: str) -> dict[str, object]:
    store = FrontierStore(root)
    try: grants = store.project_folder_grants(project_id)
    finally: store.close()
    return {"project_id": project_id, "grants": grants}


def grant_project_folder(root: Path, project_id: str, folder: Path, operation: str) -> dict[str, object]:
    store = FrontierStore(root)
    try: grant_id = store.grant_project_folder(project_id, folder, operation)
    finally: store.close()
    return {"id": grant_id, "project_id": project_id, "path": str(folder.resolve()), "operation": operation}


def revoke_project_folder(root: Path, grant_id: str) -> dict[str, object]:
    store = FrontierStore(root)
    try: store.revoke_project_folder_grant(grant_id)
    finally: store.close()
    return {"id": grant_id, "revoked": True}


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


def retry_job(root: Path, job_id: str) -> dict[str, object]:
    store = FrontierStore(root)
    try: return store.retry_job(job_id)
    finally: store.close()


def generations(root: Path, project_id: str | None = None, generation_id: str | None = None) -> dict[str, object]:
    store = FrontierStore(root)
    try:
        if generation_id is not None:
            return store.generation(generation_id)
        return {"project_id": project_id, "generations": store.generations(project_id)}
    finally:
        store.close()


def generate_local(root: Path, project_id: str, runtime: str, model: str, prompt: str, session_id: str | None = None, context_length: int | None = None, cpu_threads: int | None = None, batch_size: int | None = None, gpu_layers: int | None = None, keep_alive: str = "15m") -> dict[str, object]:
    store = FrontierStore(root)
    try:
        profile = plan_ollama_inference([model], context_length, cpu_threads, batch_size, gpu_layers, keep_alive) if runtime == "ollama" else {}
        generation_id = store.create_generation(project_id, runtime, model, prompt, session_id, profile)
        if runtime != "ollama":
            job_id = str(store.generation(generation_id)["job_id"])
            store.claim_job(job_id)
            store.fail_job(job_id, {"code": "FR-GENERATION-RUNTIME", "detail": f"Unsupported local runtime: {runtime}"})
            return store.generation(generation_id)
        if not profile["supported"]:
            job_id = str(store.generation(generation_id)["job_id"])
            store.claim_job(job_id)
            store.fail_job(job_id, {"code": "FR-INFERENCE-PROFILE", "reasons": profile["reasons"]})
            return store.generation(generation_id)
        list(run_generation(store, generation_id, stream_ollama(model, prompt, profile["options"], str(profile["keep_alive"]), profile["runtime_probe"])))
        return store.generation(generation_id)
    finally:
        store.close()


def inference_plan(models: list[str], context_length: int | None = None, cpu_threads: int | None = None, batch_size: int | None = None, gpu_layers: int | None = None, keep_alive: str = "15m", concurrency: int = 1) -> dict[str, object]:
    return {"plan": plan_ollama_inference(models, context_length, cpu_threads, batch_size, gpu_layers, keep_alive, concurrency)}


def warmup_local_model(model: str, context_length: int | None = None, cpu_threads: int | None = None, batch_size: int | None = None, gpu_layers: int | None = None, keep_alive: str = "15m") -> dict[str, object]:
    plan = plan_ollama_inference([model], context_length, cpu_threads, batch_size, gpu_layers, keep_alive)
    if not plan["supported"]:
        return {"plan": plan, "warmup": None}
    return {"plan": plan, "warmup": warmup_ollama(model, plan["options"], str(plan["keep_alive"]), plan["runtime_probe"])}


def install_ollama_model(root: Path, project_id: str, model: str) -> dict[str, object]:
    store = FrontierStore(root)
    try:
        return install_local_ollama_model(store, project_id, model)
    finally:
        store.close()


def search_huggingface_models(query: str, limit: int = 10) -> dict[str, object]:
    return {"query": query, "models": HuggingFaceHub().search_models(query, limit)}


def plan_huggingface_model_download(repository_id: str, filename: str, destination: Path, revision: str = "main", interactive: bool = False) -> dict[str, object]:
    return {"plan": HuggingFaceHub().download_plan(repository_id, filename, destination, revision, interactive)}


def download_huggingface_model(root: Path, repository_id: str, filename: str, destination: Path, revision: str = "main", expected_sha256: str | None = None) -> dict[str, object]:
    registry = ModelRegistry(root / "models.sqlite3")
    try:
        return registry.download_and_register(HuggingFaceHub(), repository_id, filename, destination, revision, expected_sha256)
    finally:
        registry.close()


def start_huggingface_model_transfer(root: Path, project_id: str, repository_id: str, filename: str, destination: Path, revision: str = "main", expected_sha256: str | None = None) -> dict[str, object]:
    store = FrontierStore(root)
    try:
        record = create_model_transfer(store, HuggingFaceHub(), project_id, repository_id, filename, destination, revision, expected_sha256)
    finally:
        store.close()
    worker_pid = _spawn_model_transfer_worker(root, str(record["id"]))
    return {**record, "worker_pid": worker_pid}


def huggingface_model_transfer(root: Path, job_id: str) -> dict[str, object]:
    store = FrontierStore(root)
    try:
        record = store.job(job_id)
        if record["operation"] != MODEL_TRANSFER_OPERATION:
            raise ValueError("Job is not a Hugging Face model transfer.")
        return record
    finally:
        store.close()


def retry_huggingface_model_transfer(root: Path, job_id: str) -> dict[str, object]:
    store = FrontierStore(root)
    try:
        original = store.job(job_id)
        if original["operation"] != MODEL_TRANSFER_OPERATION:
            raise ValueError("Job is not a Hugging Face model transfer.")
        record = store.retry_job(job_id)
    finally:
        store.close()
    worker_pid = _spawn_model_transfer_worker(root, str(record["id"]))
    return {**record, "worker_pid": worker_pid}


def _spawn_model_transfer_worker(root: Path, job_id: str) -> int:
    log_directory = root / "model-transfer-logs"
    log_directory.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-m", "frontier_engine.cli", "model-download-run", "--json", "--data-dir", str(root), "--job-id", job_id]
    options: dict[str, object] = {"cwd": str(Path.cwd()), "env": {**os.environ, "FRONTIER_DATA_DIR": str(root)}, "close_fds": True}
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW
    else:
        options["start_new_session"] = True
    try:
        with (log_directory / f"{job_id}.log").open("ab") as log:
            options["stdout"] = log
            options["stderr"] = log
            process = subprocess.Popen(command, **options)
    except OSError as error:
        store = FrontierStore(root)
        try:
            store.claim_job(job_id)
            store.fail_job(job_id, {"code": "FR-HF-TRANSFER-START", "detail": str(error)})
        finally:
            store.close()
        raise RuntimeError("FR-HF-TRANSFER-START") from error
    return process.pid


def automation_catalog(root: Path, project_id: str | None = None) -> dict[str, object]:
    store = AutomationStore(root / "automations.sqlite3")
    try:
        pipelines = store.pipelines(project_id)
        pipeline_ids = {str(pipeline["id"]) for pipeline in pipelines}
        runs = [run for run in store.run_records() if str(run["automation_id"]) in pipeline_ids]
        return {"capabilities": pipeline_capabilities(), "pipelines": pipelines, "runs": runs}
    finally:
        store.close()


def create_automation(root: Path, project_id: str, name: str, steps: list[dict[str, object]], schedule: dict[str, object]) -> dict[str, object]:
    frontier = FrontierStore(root)
    try:
        frontier.require_active_project(project_id)
    finally:
        frontier.close()
    store = AutomationStore(root / "automations.sqlite3")
    try:
        return store.create_pipeline(project_id, name, steps, schedule)
    finally:
        store.close()


def start_automation(root: Path, automation_id: str, dry_run: bool = True, external_approved: bool = False, trigger_kind: str = "manual") -> dict[str, object]:
    store = AutomationStore(root / "automations.sqlite3")
    try:
        record = store.queue_run(automation_id, dry_run, external_approved, trigger_kind)
    finally:
        store.close()
    return record if dry_run else {**record, "worker_pid": _spawn_automation_worker(root, str(record["id"]))}


def automation_run(root: Path, run_id: str) -> dict[str, object]:
    store = AutomationStore(root / "automations.sqlite3")
    try:
        return store.run_record(run_id)
    finally:
        store.close()


def cancel_automation(root: Path, run_id: str) -> dict[str, object]:
    store = AutomationStore(root / "automations.sqlite3")
    try:
        return store.request_cancellation(run_id)
    finally:
        store.close()


def retry_automation(root: Path, run_id: str, external_approved: bool = False) -> dict[str, object]:
    store = AutomationStore(root / "automations.sqlite3")
    try:
        record = store.retry_run(run_id, external_approved)
    finally:
        store.close()
    return {**record, "worker_pid": _spawn_automation_worker(root, str(record["id"]))}


def run_due_automations(root: Path) -> dict[str, object]:
    store = AutomationStore(root / "automations.sqlite3")
    try:
        due = store.due_pipelines()
        queued = []
        approval_required = []
        for pipeline in due:
            if pipeline["external_effects"]:
                approval_required.append(pipeline["id"])
            else:
                record = store.queue_due_run(str(pipeline["id"]))
                if record is not None:
                    queued.append(record)
    finally:
        store.close()
    started = [{**record, "worker_pid": _spawn_automation_worker(root, str(record["id"]))} for record in queued]
    return {"started": started, "approval_required": approval_required}


def _spawn_automation_worker(root: Path, run_id: str) -> int:
    log_directory = root / "automation-logs"
    log_directory.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-m", "frontier_engine.cli", "automation-run-worker", "--json", "--data-dir", str(root), "--automation-run-id", run_id]
    options: dict[str, object] = {"cwd": str(Path.cwd()), "env": {**os.environ, "FRONTIER_DATA_DIR": str(root)}, "close_fds": True}
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW
    else:
        options["start_new_session"] = True
    try:
        with (log_directory / f"{run_id}.log").open("ab") as log:
            options["stdout"] = log
            options["stderr"] = log
            process = subprocess.Popen(command, **options)
    except OSError as error:
        store = AutomationStore(root / "automations.sqlite3")
        try:
            store.claim_run(run_id)
            store.complete_run(run_id, "failed", {"code": "FR-AUTO-WORKER-START", "detail": str(error)})
        finally:
            store.close()
        raise RuntimeError("FR-AUTO-WORKER-START") from error
    return process.pid


def execute_shell(root: Path, project_id: str, working_directory: Path, command: list[str], timeout_seconds: float) -> dict[str, object]:
    store = FrontierStore(root)
    try:
        return execute_project_shell(store, project_id, working_directory, command, timeout_seconds)
    finally:
        store.close()


def workspace_tool(root: Path, project_id: str, workspace: Path, action: str, relative_path: str | None = None, content: str | None = None) -> dict[str, object]:
    store = FrontierStore(root); agent = AgentStateStore(root / "agent.sqlite3")
    try:
        tools = ProjectWorkspaceTools(store, agent, project_id, workspace)
        if action == "list": return {"files": tools.list_files()}
        if relative_path is None: raise ValueError("Workspace read/write requires a relative path.")
        if action == "read": return {"path": relative_path, "content": tools.read_file(relative_path)}
        if action == "write":
            if content is None: raise ValueError("Workspace write requires content.")
            return {"path": relative_path, "written": str(tools.write_file(relative_path, content))}
        raise ValueError("Unsupported workspace tool action.")
    finally:
        agent.close(); store.close()


def run_agent(root: Path, project_id: str, model: str, prompt: str, skill_ids: list[str] | None = None) -> dict[str, object]:
    store = FrontierStore(root)
    try: store.require_active_project(project_id)
    finally: store.close()
    state = AgentStateStore(root / "agent.sqlite3")
    try: return run_local_agent(state, project_id, model, prompt, skill_ids=skill_ids)
    finally: state.close()


def probe_integrations(root: Path, approved: bool) -> dict[str, object]:
    ledger = IntegrationLedger(root / "integrations.sqlite3")
    try:
        result = probe_mcp_servers(approved)
        for connector in result["connectors"]:
            ledger.record(str(connector["id"]), "probe", "succeeded")
        for failure in result["failures"]:
            ledger.record(str(failure["id"]), "probe", "failed", str(failure["code"]))
        return {**result, "events": ledger.events()}
    finally:
        ledger.close()


def invoke_mcp(root: Path, project_id: str, server_id: str, tool_name: str, arguments: dict[str, object], approved: bool) -> dict[str, object]:
    frontier = FrontierStore(root)
    try:
        frontier.require_active_project(project_id)
    finally:
        frontier.close()
    ledger = IntegrationLedger(root / "integrations.sqlite3")
    try:
        try:
            result = call_mcp_tool(server_id, tool_name, arguments, approved)
        except Exception as error:
            code = str(error).split(":", 1)[0] if str(error).startswith("FR-") else "FR-MCP-CALL"
            ledger.record(server_id, f"tool:{tool_name}", "failed", code, project_id)
            raise
        ledger.record(server_id, f"tool:{tool_name}", "succeeded", project_id=project_id)
        return {**result, "events": ledger.events(project_id)}
    finally:
        ledger.close()


def serve_kernel_stdio(root: Path) -> None:
    service = LoopbackService(data_root=root)
    try:
        for line in sys.stdin:
            if not line.strip():
                continue
            try:
                response = service._rpc(json.loads(line))
            except (TypeError, ValueError, json.JSONDecodeError) as error:
                response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(error)}}
            print(json.dumps(response, sort_keys=True), flush=True)
    finally:
        service.close()


def agent_activity(root: Path, project_id: str) -> dict[str, object]:
    store = FrontierStore(root)
    try: store.require_active_project(project_id)
    finally: store.close()
    state = AgentStateStore(root / "agent.sqlite3")
    try:
        tool_calls = [
            {
                "id": row["id"],
                "tool_name": row["tool_name"],
                "created_at": row["created_at"],
                "request": json.loads(row["request"]),
                "state": row["state"],
                "result": json.loads(row["result"]),
            }
            for row in state.tool_calls(project_id)
        ]
        return {
            "project_id": project_id,
            "plan": state.plan(project_id),
            "todos": [todo.__dict__ for todo in state.todos(project_id)],
            "tool_calls": tool_calls,
        }
    finally: state.close()


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


def _require_artifact_version(root: Path, version_id: str) -> None:
    store = FrontierStore(root)
    try:
        if store.connection.execute("SELECT 1 FROM artifact_versions WHERE id = ?", (version_id,)).fetchone() is None:
            raise KeyError(f"Artifact version not found: {version_id}")
    finally: store.close()


def create_annotation(root: Path, version_id: str, target_kind: str, selector: str, body: str) -> dict[str, object]:
    _require_artifact_version(root, version_id)
    annotation = AnnotationStore(root / "annotations.sqlite3")
    try:
        identifier = annotation.create(version_id, target_kind, json.loads(selector), body)
        return {"id": identifier, "artifact_version_id": version_id, "target_kind": target_kind, "selector": json.loads(selector), "body": body}
    finally: annotation.close()


def annotations(root: Path, version_id: str) -> dict[str, object]:
    _require_artifact_version(root, version_id)
    annotation = AnnotationStore(root / "annotations.sqlite3")
    try: return {"artifact_version_id": version_id, "annotations": [item.__dict__ for item in annotation.list_open(version_id)]}
    finally: annotation.close()


def consume_annotations(root: Path, annotation_ids: tuple[str, ...]) -> dict[str, object]:
    annotation = AnnotationStore(root / "annotations.sqlite3")
    try: return {"annotations": [item.__dict__ for item in annotation.consume(annotation_ids)]}
    finally: annotation.close()


def review_scientific_claims(root: Path) -> dict[str, object]:
    ledger = ClaimLedger(root / "claims.sqlite3")
    try:
        records = ledger.list()
        claims = tuple(Claim(str(record["id"]), str(record["text"]), str(record["claim_type"]), tuple(str(item["evidence_uri"]) for item in record["evidence"])) for record in records)
        return {"findings": [finding.__dict__ for finding in review_claims(claims)]}
    finally: ledger.close()


def search_artifacts(root: Path, query: str, project_id: str | None = None, media_type: str | None = None) -> dict[str, object]:
    store = FrontierStore(root)
    try: records = store.search_artifacts(query, project_id, media_type)
    finally: store.close()
    return {"query": query, "project_id": project_id, "media_type": media_type, "artifacts": records}


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
    parser.add_argument("command", choices=("doctor", "status", "config", "serve", "kernel-stdio", "url", "service-status", "logs", "stop", "environments", "create-environment", "create-r-environment", "install-packages", "install-r-packages", "render-preview", "storage-transfer", "s3-transfer", "remote-compute", "verify-runtime-bundle", "projects", "set-project-instructions", "sessions", "star-session", "set-session-reasoning", "search-sessions", "archive-project", "project-folders", "grant-project-folder", "revoke-project-folder", "jobs", "cancel-job", "retry-job", "automations", "create-automation", "automation-start", "automation-status", "automation-cancel", "automation-retry", "automation-due", "automation-run-worker", "agent-workspace", "agent-run", "agent-activity", "integration-probe", "mcp-call", "shell-exec", "generations", "generate-local", "inference-plan", "warmup-model", "install-ollama-model", "model-search", "model-download-plan", "model-download-start", "model-download-status", "model-download-retry", "model-download-run", "model-download", "artifacts", "search-artifacts", "artifact-versions", "annotations", "consume-annotations", "review", "literature", "claims", "set-claim-status", "connectors", "skills", "extensions", "export", "import"))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--name")
    parser.add_argument("--package", action="append")
    parser.add_argument("--repository", default="https://cloud.r-project.org")
    parser.add_argument("--channel", default="cran")
    parser.add_argument("--max-bytes", type=int, default=1_000_000)
    parser.add_argument("--endpoint")
    parser.add_argument("--prefix")
    parser.add_argument("--object-key")
    parser.add_argument("--approved", action="store_true")
    parser.add_argument("--s3-container")
    parser.add_argument("--s3-region", default="us-east-1")
    parser.add_argument("--s3-access-key-env", default="AWS_ACCESS_KEY_ID")
    parser.add_argument("--s3-secret-key-env", default="AWS_SECRET_ACCESS_KEY")
    parser.add_argument("--s3-session-token-env", default="AWS_SESSION_TOKEN")
    parser.add_argument("--compute-target", choices=("ssh", "slurm", "cloud"))
    parser.add_argument("--compute-endpoint")
    parser.add_argument("--compute-command", action="append")
    parser.add_argument("--compute-cpu", type=int, default=1)
    parser.add_argument("--compute-memory-mb", type=int, default=1024)
    parser.add_argument("--compute-timeout", type=int, default=300)
    parser.add_argument("--compute-cost", type=float, default=0)
    parser.add_argument("--compute-egress", type=int, default=0)
    parser.add_argument("--compute-working-directory")
    parser.add_argument("--compute-approved", action="store_true")
    parser.add_argument("--project-id")
    parser.add_argument("--folder", type=Path)
    parser.add_argument("--folder-operation", choices=("read", "write"))
    parser.add_argument("--folder-grant-id")
    parser.add_argument("--session-id")
    parser.add_argument("--title")
    parser.add_argument("--parent-session-id")
    parser.add_argument("--instructions")
    parser.add_argument("--reasoning-effort", choices=("compact", "standard", "extended"), default="standard")
    parser.add_argument("--starred", choices=("true", "false"))
    parser.add_argument("--operation")
    parser.add_argument("--working-directory", type=Path)
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--workspace-action", choices=("list", "read", "write"))
    parser.add_argument("--path")
    parser.add_argument("--text")
    parser.add_argument("--shell-arg", action="append")
    parser.add_argument("--timeout-seconds", type=float, default=30)
    parser.add_argument("--job-id")
    parser.add_argument("--automation-id")
    parser.add_argument("--automation-run-id")
    parser.add_argument("--steps-json")
    parser.add_argument("--schedule-json", default='{"kind":"manual"}')
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--external-approved", action="store_true")
    parser.add_argument("--skill-id", action="append")
    parser.add_argument("--mcp-server-id")
    parser.add_argument("--mcp-tool-name")
    parser.add_argument("--mcp-arguments", default="{}")
    parser.add_argument("--generation-id")
    parser.add_argument("--runtime")
    parser.add_argument("--model")
    parser.add_argument("--profile-model", action="append")
    parser.add_argument("--context-length", type=int)
    parser.add_argument("--cpu-threads", type=int)
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--gpu-layers", type=int)
    parser.add_argument("--keep-alive", default="15m")
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--repository-id")
    parser.add_argument("--filename")
    parser.add_argument("--revision", default="main")
    parser.add_argument("--expected-sha256")
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--prompt")
    parser.add_argument("--artifact-id")
    parser.add_argument("--artifact-version-id")
    parser.add_argument("--target-kind")
    parser.add_argument("--selector")
    parser.add_argument("--body")
    parser.add_argument("--annotation-id", action="append")
    parser.add_argument("--media-type")
    parser.add_argument("--content", default="")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--bundle-root", type=Path)
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
    parser.add_argument("--background", action="store_true")
    parser.add_argument("--background-child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--tail", type=int, default=100)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--loopback-port", type=int, default=0, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = args.data_dir if args.data_dir is not None else data_root()
    if args.command == "doctor":
        result = doctor()
    elif args.command == "status":
        result = status(root)
    elif args.command == "config":
        result = {"data_root": str(root), "environment_variable": "FRONTIER_DATA_DIR"}
    elif args.command == "serve":
        if args.duration_seconds is not None and args.duration_seconds < 0:
            parser.error("serve --duration-seconds must be non-negative")
        if args.background and args.background_child:
            parser.error("serve accepts only one background mode")
        if args.background:
            result = start_background_service(root)
            print(json.dumps(result, sort_keys=True) if args.json else json.dumps(result, indent=2, sort_keys=True))
            return
        service = LoopbackService(args.loopback_port, root)
        service.start()
        public_result = {"url": service.url, "status_path": "/status", "rpc_path": "/rpc", "authorization": "Bearer"}
        if not args.background_child:
            print(json.dumps({**public_result, "token": service.token}, sort_keys=True) if args.json else json.dumps({**public_result, "token": service.token}, indent=2, sort_keys=True))
        stop_event = threading.Event()
        previous_handler = signal.signal(signal.SIGTERM, lambda *_: stop_event.set())
        try:
            stop_event.wait(args.duration_seconds)
        except KeyboardInterrupt:
            pass
        finally:
            signal.signal(signal.SIGTERM, previous_handler)
            service.close()
        return
    elif args.command == "kernel-stdio":
        serve_kernel_stdio(root)
        return
    elif args.command == "url":
        result = _service_status(root)
        if not result["running"]: parser.error("No Frontier control-plane service is running")
    elif args.command == "service-status":
        result = _service_status(root)
    elif args.command == "logs":
        result = service_logs(root, args.tail)
    elif args.command == "stop":
        result = stop_background_service(root)
    elif args.command == "environments":
        result = {"manifests": list_manifests(root), "probe": probe_environment(args.language or "python")}
    elif args.command == "create-environment":
        if args.name is None:
            parser.error("create-environment requires --name")
        result = create_python_environment(root, args.name)
    elif args.command == "create-r-environment":
        if args.name is None:
            parser.error("create-r-environment requires --name")
        result = create_r_environment(root, args.name)
    elif args.command == "install-packages":
        if args.name is None or not args.package:
            parser.error("install-packages requires --name and one or more --package")
        result = install_python_packages(root, args.name, args.package)
    elif args.command == "install-r-packages":
        if args.name is None or not args.package:
            parser.error("install-r-packages requires --name and one or more --package")
        result = install_r_packages(root, args.name, args.package, args.repository, args.channel)
    elif args.command == "render-preview":
        if args.media_type is None:
            parser.error("render-preview requires --media-type")
        result = render_preview(args.media_type, args.content, args.max_bytes)
    elif args.command == "storage-transfer":
        if args.endpoint is None or args.prefix is None or args.object_key is None or args.operation not in {"import", "export", "delete"}:
            parser.error("storage-transfer requires --endpoint, --prefix, --object-key, and import/export/delete --operation")
        profile = StorageProfile("s3_compatible", args.endpoint, "local", args.prefix, "cli-explicit")
        result = execute_local_transfer(build_manifest(profile, args.object_key, args.content.encode(), args.operation), args.approved)
    elif args.command == "s3-transfer":
        if any(value is None for value in (args.endpoint, args.prefix, args.object_key, args.s3_container)) or args.operation not in {"import", "export", "delete"}:
            parser.error("s3-transfer requires --endpoint, --s3-container, --prefix, --object-key, and import/export/delete --operation")
        access_key = os.environ.get(args.s3_access_key_env, "")
        secret_key = os.environ.get(args.s3_secret_key_env, "")
        if not access_key or not secret_key:
            parser.error("s3-transfer requires credentials in the named environment variables")
        profile = StorageProfile("s3_compatible", args.endpoint, args.s3_container, args.prefix, "cli-environment")
        credentials = S3Credentials(access_key, secret_key, os.environ.get(args.s3_session_token_env) or None)
        result = execute_s3_signed_transfer(build_manifest(profile, args.object_key, args.content.encode(), args.operation), args.s3_region, credentials, args.approved)
    elif args.command == "remote-compute":
        if args.compute_target is None or not args.compute_command or args.compute_endpoint is None:
            parser.error("remote-compute requires --compute-target, --compute-endpoint, and one or more --compute-command")
        plan = ComputePlan(args.compute_target, tuple(args.compute_command), args.compute_cpu, args.compute_memory_mb, args.compute_timeout, args.compute_cost, args.compute_egress, args.compute_endpoint, args.compute_working_directory)
        result = run_remote(plan, args.compute_approved)
    elif args.command == "verify-runtime-bundle":
        if args.manifest is None or args.bundle_root is None:
            parser.error("verify-runtime-bundle requires --manifest and --bundle-root")
        result = verify_bundle(args.manifest, args.bundle_root)
    elif args.command == "projects":
        result = create_project(root, args.name, args.instructions or "") if args.name is not None else projects(root)
    elif args.command == "set-project-instructions":
        if args.project_id is None or args.instructions is None:
            parser.error("set-project-instructions requires --project-id and --instructions")
        result = set_project_instructions(root, args.project_id, args.instructions)
    elif args.command == "sessions":
        if args.project_id is None:
            parser.error("sessions requires --project-id")
        result = create_session(root, args.project_id, args.title, args.parent_session_id, args.reasoning_effort) if args.title is not None else sessions(root, args.project_id)
    elif args.command == "star-session":
        if args.session_id is None or args.starred is None:
            parser.error("star-session requires --session-id and --starred true|false")
        result = set_session_starred(root, args.session_id, args.starred == "true")
    elif args.command == "set-session-reasoning":
        if args.session_id is None:
            parser.error("set-session-reasoning requires --session-id")
        result = set_session_reasoning_effort(root, args.session_id, args.reasoning_effort)
    elif args.command == "search-sessions":
        if args.query is None:
            parser.error("search-sessions requires --query")
        result = search_sessions(root, args.query, args.project_id)
    elif args.command == "archive-project":
        if args.project_id is None:
            parser.error("archive-project requires --project-id")
        result = archive_project(root, args.project_id)
    elif args.command == "project-folders":
        if args.project_id is None:
            parser.error("project-folders requires --project-id")
        result = project_folders(root, args.project_id)
    elif args.command == "grant-project-folder":
        if args.project_id is None or args.folder is None or args.folder_operation is None:
            parser.error("grant-project-folder requires --project-id, --folder, and --folder-operation")
        result = grant_project_folder(root, args.project_id, args.folder, args.folder_operation)
    elif args.command == "revoke-project-folder":
        if args.folder_grant_id is None:
            parser.error("revoke-project-folder requires --folder-grant-id")
        result = revoke_project_folder(root, args.folder_grant_id)
    elif args.command == "jobs":
        if args.project_id is None or args.operation is None:
            result = jobs(root)
        else:
            result = enqueue_job(root, args.project_id, args.operation)
    elif args.command == "cancel-job":
        if args.job_id is None:
            parser.error("cancel-job requires --job-id")
        result = cancel_job(root, args.job_id)
    elif args.command == "retry-job":
        if args.job_id is None:
            parser.error("retry-job requires --job-id")
        result = retry_job(root, args.job_id)
    elif args.command == "automations":
        result = automation_catalog(root, args.project_id)
    elif args.command == "create-automation":
        if args.project_id is None or args.name is None or args.steps_json is None:
            parser.error("create-automation requires --project-id, --name, and --steps-json")
        result = create_automation(root, args.project_id, args.name, json.loads(args.steps_json), json.loads(args.schedule_json))
    elif args.command == "automation-start":
        if args.automation_id is None:
            parser.error("automation-start requires --automation-id")
        result = start_automation(root, args.automation_id, not args.execute, args.external_approved)
    elif args.command == "automation-status":
        if args.automation_run_id is None:
            parser.error("automation-status requires --automation-run-id")
        result = automation_run(root, args.automation_run_id)
    elif args.command == "automation-cancel":
        if args.automation_run_id is None:
            parser.error("automation-cancel requires --automation-run-id")
        result = cancel_automation(root, args.automation_run_id)
    elif args.command == "automation-retry":
        if args.automation_run_id is None:
            parser.error("automation-retry requires --automation-run-id")
        result = retry_automation(root, args.automation_run_id, args.external_approved)
    elif args.command == "automation-due":
        result = run_due_automations(root)
    elif args.command == "automation-run-worker":
        if args.automation_run_id is None:
            parser.error("automation-run-worker requires --automation-run-id")
        result = run_pipeline(root, args.automation_run_id)
    elif args.command == "shell-exec":
        if args.project_id is None or args.working_directory is None or args.shell_arg is None:
            parser.error("shell-exec requires --project-id, --working-directory, and one or more --shell-arg values")
        result = execute_shell(root, args.project_id, args.working_directory, args.shell_arg, args.timeout_seconds)
    elif args.command == "agent-workspace":
        if args.project_id is None or args.workspace is None or args.workspace_action is None:
            parser.error("agent-workspace requires --project-id, --workspace, and --workspace-action")
        result = workspace_tool(root, args.project_id, args.workspace, args.workspace_action, args.path, args.text)
    elif args.command == "agent-run":
        if args.project_id is None or args.model is None or args.prompt is None:
            parser.error("agent-run requires --project-id, --model, and --prompt")
        result = run_agent(root, args.project_id, args.model, args.prompt, args.skill_id)
    elif args.command == "agent-activity":
        if args.project_id is None:
            parser.error("agent-activity requires --project-id")
        result = agent_activity(root, args.project_id)
    elif args.command == "generations":
        result = generations(root, args.project_id, args.generation_id)
    elif args.command == "generate-local":
        if args.project_id is None or args.runtime is None or args.model is None or args.prompt is None:
            parser.error("generate-local requires --project-id, --runtime, --model, and --prompt")
        result = generate_local(root, args.project_id, args.runtime, args.model, args.prompt, args.session_id, args.context_length, args.cpu_threads, args.batch_size, args.gpu_layers, args.keep_alive)
    elif args.command == "inference-plan":
        if not args.profile_model:
            parser.error("inference-plan requires one or more --profile-model")
        result = inference_plan(args.profile_model, args.context_length, args.cpu_threads, args.batch_size, args.gpu_layers, args.keep_alive, args.concurrency)
    elif args.command == "warmup-model":
        if args.model is None:
            parser.error("warmup-model requires --model")
        result = warmup_local_model(args.model, args.context_length, args.cpu_threads, args.batch_size, args.gpu_layers, args.keep_alive)
    elif args.command == "install-ollama-model":
        if args.project_id is None or args.model is None:
            parser.error("install-ollama-model requires --project-id and --model")
        result = install_ollama_model(root, args.project_id, args.model)
    elif args.command == "model-search":
        if args.query is None:
            parser.error("model-search requires --query")
        result = search_huggingface_models(args.query, args.limit)
    elif args.command == "model-download-plan":
        if args.repository_id is None or args.filename is None or args.destination is None:
            parser.error("model-download-plan requires --repository-id, --filename, and --destination")
        result = plan_huggingface_model_download(args.repository_id, args.filename, args.destination, args.revision, args.interactive)
    elif args.command == "model-download-start":
        if args.project_id is None or args.repository_id is None or args.filename is None or args.destination is None:
            parser.error("model-download-start requires --project-id, --repository-id, --filename, and --destination")
        result = start_huggingface_model_transfer(root, args.project_id, args.repository_id, args.filename, args.destination, args.revision, args.expected_sha256)
    elif args.command == "model-download-status":
        if args.job_id is None:
            parser.error("model-download-status requires --job-id")
        result = huggingface_model_transfer(root, args.job_id)
    elif args.command == "model-download-retry":
        if args.job_id is None:
            parser.error("model-download-retry requires --job-id")
        result = retry_huggingface_model_transfer(root, args.job_id)
    elif args.command == "model-download-run":
        if args.job_id is None:
            parser.error("model-download-run requires --job-id")
        result = run_model_transfer(root, args.job_id)
    elif args.command == "model-download":
        if args.repository_id is None or args.filename is None or args.destination is None:
            parser.error("model-download requires --repository-id, --filename, and --destination")
        result = download_huggingface_model(root, args.repository_id, args.filename, args.destination, args.revision, args.expected_sha256)
    elif args.command == "artifacts":
        if args.project_id is None:
            parser.error("artifacts requires --project-id")
        result = create_artifact(root, args.project_id, args.name, args.media_type, args.content) if args.name is not None and args.media_type is not None else artifacts(root, args.project_id)
    elif args.command == "search-artifacts":
        if args.query is None:
            parser.error("search-artifacts requires --query")
        result = search_artifacts(root, args.query, args.project_id, args.media_type)
    elif args.command == "artifact-versions":
        if args.artifact_id is None:
            parser.error("artifact-versions requires --artifact-id")
        result = artifact_versions(root, args.artifact_id)
    elif args.command == "annotations":
        if args.artifact_version_id is None:
            parser.error("annotations requires --artifact-version-id")
        if args.target_kind is not None or args.selector is not None or args.body is not None:
            if args.target_kind is None or args.selector is None or args.body is None:
                parser.error("annotation creation requires --target-kind, --selector, and --body")
            result = create_annotation(root, args.artifact_version_id, args.target_kind, args.selector, args.body)
        else:
            result = annotations(root, args.artifact_version_id)
    elif args.command == "consume-annotations":
        if not args.annotation_id:
            parser.error("consume-annotations requires one or more --annotation-id")
        result = consume_annotations(root, tuple(args.annotation_id))
    elif args.command == "review":
        result = review_scientific_claims(root)
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
    elif args.command == "integration-probe":
        result = probe_integrations(root, args.approved)
    elif args.command == "mcp-call":
        if args.project_id is None or args.mcp_server_id is None or args.mcp_tool_name is None:
            parser.error("mcp-call requires --project-id, --mcp-server-id, and --mcp-tool-name")
        mcp_arguments = json.loads(args.mcp_arguments)
        if not isinstance(mcp_arguments, dict):
            parser.error("mcp-call --mcp-arguments must be a JSON object")
        result = invoke_mcp(root, args.project_id, args.mcp_server_id, args.mcp_tool_name, mcp_arguments, args.approved)
    elif args.command == "connectors":
        result = {"connectors": connector_catalog()}
    elif args.command == "skills":
        result = {"skills": [*skill_catalog(), *discover_skills()]}
    elif args.command == "extensions":
        result = {"extensions": [*extension_catalog(), *discover_extensions()]}
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
