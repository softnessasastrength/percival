"""Offline tests for the local runner (``scripts/run_local.py``).

The runner is exercised through a real HTTP server on an ephemeral
loopback port — the same server class and routing the ``__main__``
entry uses — so what is verified is the mounted surface itself: the
static front door, and the *unmodified* ``api/health.py`` and
``api/demo.py`` handler classes behind their real paths. The demo's
dry-run-only safety property is asserted over the wire, locally, too.
"""

from __future__ import annotations

import http.client
import importlib.util
import json
import sys
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"


def _load_runner():
    spec = importlib.util.spec_from_file_location(
        "percival_run_local", SCRIPTS_DIR / "run_local.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


run_local = _load_runner()


class _RunningLocalServer:
    def __init__(self) -> None:
        self._server = run_local.build_server(0)
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True
        )

    def __enter__(self) -> "_RunningLocalServer":
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._server.shutdown()
        self._server.server_close()

    def request(self, method: str, path: str, body: bytes | None = None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            headers = (
                {"Content-Type": "application/json"} if body is not None else {}
            )
            conn.request(method, path, body=body, headers=headers)
            response = conn.getresponse()
            data = response.read()
            return response.status, response.getheader("Content-Type") or "", data
        finally:
            conn.close()


class LocalRunnerTests(unittest.TestCase):
    def test_front_door_is_served_at_root(self) -> None:
        with _RunningLocalServer() as server:
            status, content_type, data = server.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        page = data.decode("utf-8")
        self.assertIn("Percival", page)
        self.assertIn("The arrangements are my concern.", page)

    def test_health_endpoint_over_http(self) -> None:
        with _RunningLocalServer() as server:
            status, _, data = server.request("GET", "/api/health")
        self.assertEqual(status, 200)
        payload = json.loads(data)
        self.assertEqual(payload["service"], "percival-core")
        self.assertEqual(payload["status"], "ok")

    def test_demo_description_over_http(self) -> None:
        with _RunningLocalServer() as server:
            status, _, data = server.request("GET", "/api/demo")
        self.assertEqual(status, 200)
        payload = json.loads(data)
        self.assertEqual(payload["endpoint"], "/api/demo")
        self.assertFalse(payload["side_effects"])

    def test_demo_post_is_a_dry_run(self) -> None:
        body = json.dumps({"message": "Good evening."}).encode()
        with _RunningLocalServer() as server:
            status, _, data = server.request("POST", "/api/demo", body)
        self.assertEqual(status, 200)
        payload = json.loads(data)
        self.assertEqual(payload["status"], "dry_run")
        self.assertTrue(payload["dry_run"])
        self.assertFalse(payload["tool_invoked"])

    def test_demo_live_run_request_is_rejected(self) -> None:
        body = json.dumps({"message": "x", "dry_run": False}).encode()
        with _RunningLocalServer() as server:
            status, _, data = server.request("POST", "/api/demo", body)
        self.assertEqual(status, 400)
        payload = json.loads(data)
        self.assertIn("not negotiable", payload["error"])


if __name__ == "__main__":
    unittest.main()
