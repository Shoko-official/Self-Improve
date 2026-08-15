import json
import socket
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

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

    def _rpc(self, service: LoopbackService, body: dict[str, object]) -> dict[str, object]:
        request = Request(f"{service.url}/rpc", data=json.dumps(body).encode(), headers={"Authorization": f"Bearer {service.token}", "Content-Type": "application/json"}, method="POST")
        return json.load(urlopen(request))
