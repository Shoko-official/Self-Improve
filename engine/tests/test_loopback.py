import json
import socket
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from frontier_engine.loopback import LoopbackService


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
