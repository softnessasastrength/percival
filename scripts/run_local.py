#!/usr/bin/env python3
"""Run Percival's web surface locally, on loopback, stdlib only.

The same front door and API endpoints that Vercel serves in production,
run on your own machine with one command:

    python3 scripts/run_local.py            # http://127.0.0.1:8123
    python3 scripts/run_local.py --port 8200

What is served:

- ``/`` and everything under it: the static front door in ``public/``.
- ``/api/health``: the existing ``api/health.py`` handler, unmodified.
- ``/api/demo``: the existing ``api/demo.py`` handler, unmodified —
  dry-run only there, exactly as here; a body asking for
  ``dry_run: false`` is rejected by the endpoint itself.

How the mounting works: the Vercel Python runtime invokes each
entrypoint's top-level ``handler`` class (a ``BaseHTTPRequestHandler``
subclass) to service a connection. This runner does the same on one
loopback port: for each connection it peeks at the request line
(``MSG_PEEK`` — nothing is consumed), chooses the handler class for
the path, and lets that class service the connection untouched. The
entrypoint files are loaded, never modified, and no request state is
shared between them and the static file handler.
"""

from __future__ import annotations

import argparse
import importlib.util
import socket
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional, Type

ROOT = Path(__file__).resolve().parent.parent
PUBLIC_DIR = ROOT / "public"
API_DIR = ROOT / "api"
DEFAULT_PORT = 8123

# The entrypoints do ``from _percival import ...``; on Vercel the
# function's own directory is importable, so mirror that here.
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))


def _load_entrypoint(name: str):
    """Load ``api/<name>.py`` the way ``tests/test_api.py`` does."""
    spec = importlib.util.spec_from_file_location(
        f"percival_api_{name}", API_DIR / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class StaticHandler(SimpleHTTPRequestHandler):
    """The front door: static files from ``public/``."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, directory=str(PUBLIC_DIR), **kwargs)


class LocalServer(ThreadingHTTPServer):
    """One loopback port, three handler classes, routed per connection.

    ``routes`` maps exact request paths to the Vercel entrypoint
    handler classes; everything else falls through to the static
    front door.
    """

    daemon_threads = True
    routes: dict[str, Type] = {}

    def finish_request(self, request, client_address) -> None:
        self._route(request)(request, client_address, self)

    def _route(self, request) -> Type:
        try:
            peeked = request.recv(8192, socket.MSG_PEEK)
            request_line = peeked.split(b"\r\n", 1)[0].decode("iso-8859-1")
            parts = request_line.split(" ")
            if len(parts) >= 2:
                path = parts[1].split("?", 1)[0].split("#", 1)[0]
                return self.routes.get(path, StaticHandler)
        except OSError:
            pass
        return StaticHandler


def build_server(port: int, host: str = "127.0.0.1") -> LocalServer:
    """Construct the local server with the real entrypoint handlers."""
    health = _load_entrypoint("health")
    demo = _load_entrypoint("demo")
    server = LocalServer((host, port), StaticHandler)
    server.routes = {
        "/api/health": health.handler,
        "/api/demo": demo.handler,
    }
    return server


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run Percival's web surface locally (loopback only)."
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"port to bind (default {DEFAULT_PORT})",
    )
    args = parser.parse_args(argv)

    try:
        server = build_server(args.port)
    except OSError as exc:
        print(f"Percival: could not bind 127.0.0.1:{args.port} — {exc}")
        return 1

    port = server.server_address[1]
    print("Percival — local service", flush=True)
    print(f"  Front door:  http://127.0.0.1:{port}/", flush=True)
    print("  Endpoints:   /api/health  ·  /api/demo (dry-run only)", flush=True)
    print("The arrangements are my concern. Stop with Control-C.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nPercival: stood down.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
