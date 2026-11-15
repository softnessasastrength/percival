"""GET /api/health — Percival Core health, as facts.

Reports the service name, the foundation package version, and which
foundation modules import cleanly in this runtime. It performs no
writes and grants nothing.
"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler
from typing import Any, Optional

from _percival import health_payload, serve


def respond(method: str, body: Optional[bytes]) -> tuple[int, dict]:
    if method in ("GET", "HEAD"):
        return 200, health_payload()
    return 405, {"error": f"method {method} not allowed; use GET"}


class handler(BaseHTTPRequestHandler):
    """The top-level name Vercel's Python runtime requires, defined in
    this file as its static analysis insists; the work is shared."""

    def do_GET(self) -> None:
        serve(self, respond)

    def do_HEAD(self) -> None:
        serve(self, respond)

    def do_POST(self) -> None:
        serve(self, respond)

    def do_PUT(self) -> None:
        serve(self, respond)

    def do_DELETE(self) -> None:
        serve(self, respond)

    def log_message(self, format: str, *args: Any) -> None:
        pass  # outcomes are reported in the payloads, not the log
