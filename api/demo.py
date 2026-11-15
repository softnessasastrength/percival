"""POST /api/demo — a registry/executor dry-run demonstration.

Runs the foundation executor exactly once, in dry-run mode, against a
registry constructed in code for this request: one demonstration agent,
one inert echo tool (``side_effects=False``), one narrow grant. The
tool is never invoked, nothing is sent, booked, or spent, and the audit
trail lives only for the duration of the invocation. ``GET`` returns a
plain description of the endpoint.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler
from typing import Any, Optional

from _percival import DemoError, demo_description, run_demo, serve


def respond(method: str, body: Optional[bytes]) -> tuple[int, dict]:
    if method in ("GET", "HEAD"):
        return 200, demo_description()
    if method != "POST":
        return 405, {"error": f"method {method} not allowed; use GET or POST"}
    try:
        arguments = json.loads(body.decode("utf-8")) if body else {}
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return 400, {"error": f"request body is not valid JSON: {exc}"}
    try:
        return 200, run_demo(arguments)
    except DemoError as exc:
        return 400, {"error": str(exc)}


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
