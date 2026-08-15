"""Authenticated loopback-only status service."""

from __future__ import annotations

import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class LoopbackService:
    def __init__(self, port: int = 0) -> None:
        self.token = secrets.token_urlsafe(32)
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
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def _handler(self) -> type[BaseHTTPRequestHandler]:
        token = self.token
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if self.path != "/status": self.send_error(404); return
                if self.headers.get("Authorization") != f"Bearer {token}": self.send_error(401); return
                payload = json.dumps({"bind": "127.0.0.1", "authentication": "bearer", "status": "healthy"}).encode()
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(payload))); self.end_headers(); self.wfile.write(payload)
            def log_message(self, format: str, *args: object) -> None: pass
        return Handler
