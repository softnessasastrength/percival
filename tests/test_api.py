"""Offline tests for the Vercel serverless surface (``api/``).

The handler classes are exercised through a real local HTTP server on
an ephemeral port — the same ``BaseHTTPRequestHandler`` contract the
Vercel Python runtime uses — so what is verified here is the handler
behaviour itself, not a mock of it. No network beyond loopback, no
deployment, no side effects: the demo endpoint is dry-run by design,
and these tests also assert that it stays that way.
"""

from __future__ import annotations

import http.client
import importlib
import importlib.util
import json
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API_DIR = ROOT / "api"

if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))


def _load_entrypoint(name: str):
    spec = importlib.util.spec_from_file_location(
        f"percival_api_{name}", API_DIR / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


health = _load_entrypoint("health")
demo = _load_entrypoint("demo")
surface = importlib.import_module("_percival")


class _RunningServer:
    def __init__(self, handler_class) -> None:
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), handler_class)
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self) -> "_RunningServer":
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._server.shutdown()
        self._server.server_close()

    def request(self, method: str, body: bytes | None = None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.request(method, "/", body=body)
            response = conn.getresponse()
            data = response.read()
            return response.status, json.loads(data) if data else {}
        finally:
            conn.close()


class HealthEndpointTests(unittest.TestCase):
    def test_payload_reports_foundation_facts(self) -> None:
        payload = surface.health_payload()
        self.assertEqual(payload["service"], "percival-core")
        self.assertEqual(payload["status"], "ok")
        import percival_core

        self.assertEqual(payload["version"], percival_core.__version__)
        modules = payload["foundation"]["modules"]
        self.assertEqual(
            set(modules), {"registry", "audit", "executor", "bring_to_me"}
        )
        self.assertTrue(all(modules.values()), modules)
        self.assertTrue(payload["foundation"]["all_present"])

    def test_get_over_http(self) -> None:
        with _RunningServer(health.handler) as server:
            status, payload = server.request("GET")
        self.assertEqual(status, 200)
        self.assertEqual(payload["service"], "percival-core")

    def test_post_is_refused(self) -> None:
        with _RunningServer(health.handler) as server:
            status, payload = server.request("POST", b"{}")
        self.assertEqual(status, 405)
        self.assertIn("error", payload)


class DemoEndpointTests(unittest.TestCase):
    def test_dry_run_via_core_logic(self) -> None:
        result = surface.run_demo({"message": "Good evening."})
        self.assertEqual(result["status"], "dry_run")
        self.assertTrue(result["dry_run"])
        self.assertFalse(result["tool_invoked"])
        self.assertGreaterEqual(result["audit_events_recorded"], 1)

    def test_get_describes_endpoint_over_http(self) -> None:
        with _RunningServer(demo.handler) as server:
            status, payload = server.request("GET")
        self.assertEqual(status, 200)
        self.assertEqual(payload["endpoint"], "/api/demo")
        self.assertFalse(payload["side_effects"])

    def test_post_over_http_is_a_dry_run(self) -> None:
        body = json.dumps({"message": "Good evening."}).encode()
        with _RunningServer(demo.handler) as server:
            status, payload = server.request("POST", body)
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "dry_run")
        self.assertFalse(payload["tool_invoked"])

    def test_live_run_request_is_rejected(self) -> None:
        body = json.dumps({"message": "x", "dry_run": False}).encode()
        with _RunningServer(demo.handler) as server:
            status, payload = server.request("POST", body)
        self.assertEqual(status, 400)
        self.assertIn("not negotiable", payload["error"])

    def test_invalid_json_is_rejected(self) -> None:
        with _RunningServer(demo.handler) as server:
            status, payload = server.request("POST", b"not json")
        self.assertEqual(status, 400)
        self.assertIn("not valid JSON", payload["error"])

    def test_unrecognised_fields_are_rejected(self) -> None:
        with self.assertRaises(surface.DemoError):
            surface.run_demo({"message": "x", "tool": "anything"})

    def test_non_object_body_is_rejected(self) -> None:
        with self.assertRaises(surface.DemoError):
            surface.run_demo(["not", "an", "object"])

    def test_overlong_message_is_rejected(self) -> None:
        with self.assertRaises(surface.DemoError):
            surface.run_demo({"message": "x" * (surface.MAX_DEMO_MESSAGE_CHARS + 1)})

    def test_demo_tool_has_no_side_effects(self) -> None:
        registry, _, _ = surface.build_demo()
        spec = registry.tool(surface.DEMO_TOOL)
        self.assertIsNotNone(spec)
        self.assertFalse(spec.side_effects)


class DeploymentShapeTests(unittest.TestCase):
    def test_entrypoints_define_handler(self) -> None:
        for module in (health, demo):
            self.assertTrue(hasattr(module, "handler"))

    def test_front_door_states_charter_and_pending_status(self) -> None:
        page = (ROOT / "public" / "index.html").read_text(encoding="utf-8")
        self.assertIn("The arrangements are my concern.", page)
        self.assertIn("awaits its owner", page)
        self.assertIn("/api/health", page)
        self.assertIn("/api/demo", page)


if __name__ == "__main__":
    unittest.main()
