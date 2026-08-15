import json
import socket
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

from frontier_engine.agent_state import AgentStateStore
from frontier_engine.loopback import LoopbackService
from frontier_engine.store import FrontierStore


class LoopbackTests(unittest.TestCase):
    def test_status_is_loopback_and_authenticated(self) -> None:
        service = LoopbackService(); service.start()
        try:
            with self.assertRaises(HTTPError) as denied: urlopen(f"{service.url}/status")
            self.assertEqual(denied.exception.code, 401); denied.exception.close()
            request = Request(f"{service.url}/status", headers={"Authorization": f"Bearer {service.token}"})
            self.assertEqual(json.load(urlopen(request))["bind"], "127.0.0.1")
        finally: service.close()

    def test_service_can_bind_a_reserved_loopback_port(self) -> None:
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0)); port = reservation.getsockname()[1]
        service = LoopbackService(port); service.start()
        try: self.assertEqual(service.url, f"http://127.0.0.1:{port}")
        finally: service.close()

    def test_rpc_requires_a_token_and_returns_a_versioned_doctor_response(self) -> None:
        service = LoopbackService(); service.start()
        try:
            denied = Request(f"{service.url}/rpc", data=b'{"jsonrpc":"2.0","id":1,"method":"system.doctor"}', method="POST")
            with self.assertRaises(HTTPError) as error: urlopen(denied)
            self.assertEqual(error.exception.code, 401); error.exception.close()
            response = self._rpc(service, {"jsonrpc": "2.0", "id": "doctor", "method": "system.doctor"})
            self.assertEqual(response["id"], "doctor")
            self.assertEqual(response["result"]["protocol_version"], 1)
        finally: service.close()

    def test_rpc_reports_invalid_requests_and_unknown_methods(self) -> None:
        service = LoopbackService(); service.start()
        try:
            invalid = self._rpc(service, {"id": 1, "method": "system.doctor"})
            unknown = self._rpc(service, {"jsonrpc": "2.0", "id": 2, "method": "unknown.method"})
            self.assertEqual(invalid["error"]["code"], -32600)
            self.assertEqual(unknown["error"]["code"], -32000)
        finally: service.close()

    def test_rpc_install_returns_a_durable_job_record(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); store = FrontierStore(root); project_id = store.create_project("RPC"); store.close()
            service = LoopbackService(data_root=root); service.start()
            try:
                record = {"id": "job", "state": "failed", "events": [], "diagnostic": {"code": "FR-RUNTIME-OLLAMA-NOT-FOUND"}}
                with patch("frontier_engine.loopback.install_ollama_model", return_value=record):
                    response = self._rpc(service, {"jsonrpc": "2.0", "id": 3, "method": "runtime.install", "params": {"project_id": project_id, "model": "qwen3"}})
                self.assertEqual(response["result"]["diagnostic"]["code"], "FR-RUNTIME-OLLAMA-NOT-FOUND")
            finally: service.close()

    def test_rpc_retries_a_terminal_job_with_a_parent_link(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); store = FrontierStore(root); project_id = store.create_project("RPC"); job_id = store.create_job(project_id, "rag.ingest", {}); store.claim_job(job_id); store.fail_job(job_id, {"code": "FR-FAIL"}); store.close()
            service = LoopbackService(data_root=root); service.start()
            try:
                response = self._rpc(service, {"jsonrpc": "2.0", "id": 4, "method": "job.retry", "params": {"job_id": job_id}})
                self.assertEqual(response["result"]["parent_job_id"], job_id)
                self.assertEqual(response["result"]["state"], "queued")
            finally: service.close()

    def test_rpc_agent_run_rejects_an_unavailable_runtime_and_records_activity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); store = FrontierStore(root); project_id = store.create_project("RPC"); store.close()
            service = LoopbackService(data_root=root); service.start()
            try:
                with patch("frontier_engine.agent_runner.stream_ollama", side_effect=RuntimeError("FR-RUNTIME-OLLAMA-NOT-FOUND")):
                    response = self._rpc(service, {"jsonrpc": "2.0", "id": 5, "method": "agent.run", "params": {"project_id": project_id, "model": "qwen3", "prompt": "Run fixture"}})
                self.assertEqual(response["error"]["code"], -32000)
                state = AgentStateStore(root / "agent.sqlite3")
                try: self.assertEqual(state.tool_calls(project_id)[0]["state"], "failed")
                finally: state.close()
            finally: service.close()

    def test_rpc_project_kernel_persists_namespace_and_restart_clears_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); store = FrontierStore(root); project_id = store.create_project("Kernel"); store.close()
            service = LoopbackService(data_root=root); service.start()
            try:
                first = self._rpc(service, {"jsonrpc": "2.0", "id": 6, "method": "kernel.execute", "params": {"project_id": project_id, "code": "sample_size = 41"}})
                second = self._rpc(service, {"jsonrpc": "2.0", "id": 7, "method": "kernel.execute", "params": {"project_id": project_id, "code": "print(sample_size + 1)"}})
                self.assertEqual(first["result"]["state"], "succeeded")
                self.assertEqual(second["result"]["stdout"], "42\n")
                self.assertEqual(self._rpc(service, {"jsonrpc": "2.0", "id": 8, "method": "kernel.restart", "params": {"project_id": project_id}})["result"]["state"], "running")
                cleared = self._rpc(service, {"jsonrpc": "2.0", "id": 9, "method": "kernel.execute", "params": {"project_id": project_id, "code": "print('sample_size' in globals())"}})
                self.assertEqual(cleared["result"]["stdout"], "False\n")
            finally: service.close()

    def test_rpc_project_kernel_rejects_an_archived_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); store = FrontierStore(root); project_id = store.create_project("Archived"); store.archive_project(project_id); store.close()
            service = LoopbackService(data_root=root); service.start()
            try:
                response = self._rpc(service, {"jsonrpc": "2.0", "id": 10, "method": "kernel.execute", "params": {"project_id": project_id, "code": "print('blocked')"}})
                self.assertEqual(response["error"]["code"], -32602)
            finally: service.close()

    def _rpc(self, service: LoopbackService, body: dict[str, object]) -> dict[str, object]:
        request = Request(f"{service.url}/rpc", data=json.dumps(body).encode(), headers={"Authorization": f"Bearer {service.token}", "Content-Type": "application/json"}, method="POST")
        return json.load(urlopen(request))
