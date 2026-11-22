"""Loopback token endpoint for tab-scoped targets (ADR-0025, spike S8).

A page on an allowed origin fetches the per-run token and puts it in `document.title`; the extension
treats the window as in scope only while the token is in the title. The token is given only to a
request with an allowed `Origin` and the `X-Scope-Token` header (which forces a CORS preflight),
so a page on any other origin cannot read it.
"""

from __future__ import annotations

import secrets
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DEFAULT_PORT = 47800
HEADER = "X-Scope-Token"


def new_token() -> str:
    return "yb-" + secrets.token_hex(16)


class TokenServer:
    def __init__(self, token: str, origins: Callable[[], frozenset[str]], port: int = DEFAULT_PORT):
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _origin(self) -> str | None:
                # Host check blocks DNS rebinding; the origin must be one the user allowed.
                host = self.headers.get("Host", "")
                if host not in (f"127.0.0.1:{outer.port}", f"localhost:{outer.port}"):
                    return None
                origin = (self.headers.get("Origin") or "").lower()
                return origin if origin in origins() else None

            def _reply(self, code: int, origin: str | None = None, body: bytes = b""):
                self.send_response(code)
                if origin:
                    self.send_header("Access-Control-Allow-Origin", origin)
                    self.send_header("Access-Control-Allow-Headers", HEADER)
                    self.send_header("Vary", "Origin")
                self.send_header("Content-Type", "text/plain")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_OPTIONS(self):
                origin = self._origin()
                self._reply(204 if origin else 403, origin)

            def do_GET(self):
                origin = self._origin()
                if self.path != "/token" or not origin or self.headers.get(HEADER) != "1":
                    return self._reply(403)
                self._reply(200, origin, outer.token.encode())

        self.token = token
        self._srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.port = self._srv.server_port
        self._thread = threading.Thread(target=self._srv.serve_forever, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._srv.shutdown()
        self._srv.server_close()
