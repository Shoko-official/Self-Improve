"""Authenticated, loopback-only JSON-RPC control service."""

from __future__ import annotations

import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from frontier_engine.__main__ import doctor
from frontier_engine.agent_runner import run_local_agent
from frontier_engine.agent_state import AgentStateStore
from frontier_engine.kernels import PythonKernel, RKernel
from frontier_engine.runtime_install import install_ollama_model
from frontier_engine.runtimes import probe_ollama
from frontier_engine.store import FrontierStore


class LoopbackService:
    def __init__(self, port: int = 0, data_root: Path | None = None) -> None:
        self.token = secrets.token_urlsafe(32)
        self.data_root = data_root
        self._kernels: dict[tuple[str, str], PythonKernel | RKernel] = {}
        self._kernel_lock = threading.Lock()
        self._server = ThreadingHTTPServer(("127.0.0.1", port), self._handler())
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_port}"

    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._thread.start()

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        with self._kernel_lock:
            for kernel in self._kernels.values(): kernel.close()
            self._kernels.clear()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def _rpc(self, request: object) -> dict[str, object]:
        request_id = request.get("id") if isinstance(request, dict) else None
        if not isinstance(request, dict) or request.get("jsonrpc") != "2.0" or not isinstance(request.get("method"), str): return _rpc_error(request_id, -32600, "Invalid JSON-RPC request.")
        params = request.get("params", {})
        if not isinstance(params, dict): return _rpc_error(request_id, -32602, "JSON-RPC params must be an object.")
        try: result = self._dispatch(str(request["method"]), params)
        except (KeyError, ValueError) as error: return _rpc_error(request_id, -32602, str(error))
        except RuntimeError as error: return _rpc_error(request_id, -32000, str(error))
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def _dispatch(self, method: str, params: dict[str, Any]) -> dict[str, object]:
        if method == "system.doctor": return doctor()
        if method == "runtime.probe": return probe_ollama()
        if self.data_root is None: raise RuntimeError("FR-RPC-DATA-ROOT-MISSING")
        if method == "runtime.install":
            store = FrontierStore(self.data_root)
            try: return install_ollama_model(store, _required_string(params, "project_id"), _required_string(params, "model"))
            finally: store.close()
        if method == "job.get":
            store = FrontierStore(self.data_root)
            try: return store.job(_required_string(params, "job_id"))
            finally: store.close()
        if method == "job.retry":
            store = FrontierStore(self.data_root)
            try: return store.retry_job(_required_string(params, "job_id"))
            finally: store.close()
        if method == "kernel.execute":
            project_id = _required_string(params, "project_id")
            self._require_active_project(project_id)
            code = _required_string(params, "code")
            language = _kernel_language(params)
            store = FrontierStore(self.data_root)
            try:
                job_id = store.create_job(project_id, "kernel.execute", {"code": code})
                store.claim_job(job_id)
                store.append_job_event(job_id, "kernel.started", {"kernel_state": self._kernel(project_id, language).state, "language": language})
                try:
                    result = self._kernel(project_id, language).execute(code)
                except RuntimeError as error:
                    execution = {"state": "failed", "error": str(error), "stdout": "", "stderr": ""}
                    store.append_job_event(job_id, "kernel.failed", execution)
                    job = store.fail_job(job_id, {"code": "FR-KERNEL-EXECUTION-FAILED", "detail": str(error)})
                    return {"project_id": project_id, "language": language, "execution": execution, "job": job}
                execution = result.__dict__
                if result.state == "succeeded":
                    store.append_job_event(job_id, "kernel.succeeded", execution)
                    job = store.complete_job(job_id, execution)
                else:
                    store.append_job_event(job_id, "kernel.failed", execution)
                    job = store.fail_job(job_id, {"code": "FR-KERNEL-EXECUTION-FAILED", "detail": result.error or "Kernel execution failed."})
                return {"project_id": project_id, "language": language, "execution": execution, "job": job}
            finally: store.close()
        if method == "kernel.restart":
            project_id = _required_string(params, "project_id")
            self._require_active_project(project_id)
            language = _kernel_language(params)
            kernel = self._kernel(project_id, language); kernel.restart()
            return {"project_id": project_id, "language": language, "state": kernel.state}
        if method == "kernel.status":
            project_id = _required_string(params, "project_id")
            self._require_active_project(project_id)
            language = _kernel_language(params)
            return {"project_id": project_id, "language": language, "state": self._kernels[(project_id, language)].state if (project_id, language) in self._kernels else "stopped"}
        if method == "agent.run":
            store = FrontierStore(self.data_root)
            try: store.require_active_project(_required_string(params, "project_id"))
            finally: store.close()
            state = AgentStateStore(self.data_root / "agent.sqlite3")
            try: return run_local_agent(state, _required_string(params, "project_id"), _required_string(params, "model"), _required_string(params, "prompt"))
            finally: state.close()
        raise RuntimeError("FR-RPC-METHOD-NOT-FOUND")

    def _require_active_project(self, project_id: str) -> None:
        if self.data_root is None: raise RuntimeError("FR-RPC-DATA-ROOT-MISSING")
        store = FrontierStore(self.data_root)
        try: store.require_active_project(project_id)
        finally: store.close()

    def _kernel(self, project_id: str, language: str) -> PythonKernel | RKernel:
        with self._kernel_lock:
            factory = RKernel if language == "r" else PythonKernel
            return self._kernels.setdefault((project_id, language), factory())

    def _handler(self) -> type[BaseHTTPRequestHandler]:
        token = self.token; service = self
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if self.path != "/status": self.send_error(404); return
                if self.headers.get("Authorization") != f"Bearer {token}": self.send_error(401); return
                payload = json.dumps({"bind": "127.0.0.1", "authentication": "bearer", "status": "healthy", "rpc_path": "/rpc"}).encode()
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(payload))); self.end_headers(); self.wfile.write(payload)
            def do_POST(self) -> None:
                if self.path != "/rpc": self.send_error(404); return
                if self.headers.get("Authorization") != f"Bearer {token}": self.send_error(401); return
                try: request = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
                except (ValueError, json.JSONDecodeError): self._send(400, _rpc_error(None, -32700, "Invalid JSON.")); return
                self._send(200, service._rpc(request))
            def _send(self, status: int, body: dict[str, object]) -> None:
                payload = json.dumps(body, sort_keys=True).encode(); self.send_response(status); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(payload))); self.end_headers(); self.wfile.write(payload)
            def log_message(self, format: str, *args: object) -> None: pass
        return Handler


def _required_string(params: dict[str, Any], key: str) -> str:
    value = params.get(key)
    if not isinstance(value, str) or not value.strip(): raise ValueError(f"{key} is required.")
    return value.strip()


def _kernel_language(params: dict[str, Any]) -> str:
    language = params.get("language", "python")
    if not isinstance(language, str) or language.strip().lower() not in {"python", "r"}: raise ValueError("language must be python or r.")
    return language.strip().lower()


def _rpc_error(request_id: object, code: int, message: str) -> dict[str, object]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}
