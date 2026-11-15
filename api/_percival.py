"""Shared logic for Percival's Vercel serverless surface.

This module is *not* a Vercel entrypoint: files in ``api/`` whose names
begin with an underscore are helper modules, not functions. The
entrypoints are ``api/health.py`` and ``api/demo.py``; each defines the
top-level ``handler`` name the Vercel Python runtime requires (a
``BaseHTTPRequestHandler`` subclass).

Safety posture of this surface, by design:

- **Read-only and dry-run only.** The health endpoint reports facts.
  The demo endpoint runs the foundation executor with ``dry_run=True``
  hard-coded; a request body asking for ``dry_run: false`` is rejected,
  so nothing reachable from this surface can invoke a tool for real.
- **No tool with a real-world effect is registered.** The only tool in
  the demo registry is an in-memory echo with ``side_effects=False`` —
  and even it is never invoked, because the run is always a dry run.
- **Nothing is granted by a request.** The demo registry, its agent,
  its tool, and its single narrow grant are constructed in code, per
  request, by this host module — the same rule the foundation enforces
  everywhere (ADR-003: models do not grant).
- **Ephemeral audit.** The audit log is an in-memory SQLite database
  created per invocation. On serverless infrastructure no filesystem
  state survives between invocations, so this surface keeps no durable
  record; it reports how many events the dry run recorded, and no more.
  A durable audit store is future work requiring an external store.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from typing import Any, Callable, Mapping, Optional

# The Vercel Python runtime bundles the project tree with the function;
# make the foundation package importable from its ``src`` layout (and
# from an installed layout, should one ever exist) before importing it.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _candidate in (os.path.join(_ROOT, "src"), _ROOT):
    if _candidate not in sys.path:
        sys.path.insert(0, _candidate)

from percival_core import (  # noqa: E402  (path setup must come first)
    AuditLog,
    Executor,
    TaskRequest,
    ToolRegistry,
    ToolSpec,
    __version__,
)

SERVICE = "percival-core"
DEMO_AGENT = "percival.demo"
DEMO_TOOL = "percival.echo"
DEMO_CAPABILITY = "echo"
DEMO_SCOPE = "demo"
MAX_DEMO_MESSAGE_CHARS = 200
_FOUNDATION_MODULES = ("registry", "audit", "executor", "bring_to_me")


class DemoError(ValueError):
    """A demo request the surface refuses, with a plain reason."""


# -- payloads -----------------------------------------------------------


def foundation_modules() -> dict[str, bool]:
    """Report which foundation modules import cleanly, honestly."""
    present: dict[str, bool] = {}
    for name in _FOUNDATION_MODULES:
        try:
            importlib.import_module(f"percival_core.{name}")
            present[name] = True
        except Exception:
            present[name] = False
    return present


def health_payload() -> dict[str, Any]:
    modules = foundation_modules()
    return {
        "service": SERVICE,
        "version": __version__,
        "status": "ok",
        "runtime": "vercel-python",
        "foundation": {
            "modules": modules,
            "all_present": all(modules.values()),
        },
        "audit_store": (
            "ephemeral: in-memory SQLite per invocation; "
            "serverless keeps no durable state"
        ),
    }


def demo_description() -> dict[str, Any]:
    return {
        "endpoint": "/api/demo",
        "method": "POST",
        "description": (
            "A registry/executor demonstration that runs the foundation "
            "executor in dry-run mode only. Authorization is checked, the "
            "outcome is audited (ephemerally), and the tool is never "
            "invoked."
        ),
        "tool": DEMO_TOOL,
        "capability": DEMO_CAPABILITY,
        "side_effects": False,
        "dry_run": "forced true; a body requesting dry_run:false is rejected",
        "example_body": {"message": "Good evening."},
    }


# -- the dry-run demonstration ------------------------------------------


def _echo_handler(arguments: Mapping[str, Any]) -> str:
    """Inert demo tool. Registered for completeness; the executor's dry
    run never invokes it, and it would only echo text if it ever ran."""
    return str(arguments.get("message", ""))


def build_demo() -> tuple[ToolRegistry, AuditLog, Executor]:
    """Construct the demo registry, grant, audit log, and executor.

    Everything here is host-issued, in code: one agent, one inert tool,
    one narrow grant for the ``echo`` capability in the ``demo`` scope.
    """
    audit = AuditLog(":memory:")
    registry = ToolRegistry(audit)
    registry.register_agent(
        DEMO_AGENT,
        "Percival (demonstration)",
        "Demonstration identity for the public dry-run surface.",
    )
    registry.register_tool(
        ToolSpec(
            name=DEMO_TOOL,
            description="Inert echo used only to demonstrate authorization.",
            capabilities=frozenset({DEMO_CAPABILITY}),
            handler=_echo_handler,
            side_effects=False,
        )
    )
    registry.grant(
        DEMO_AGENT,
        DEMO_TOOL,
        {DEMO_CAPABILITY},
        granted_by="percival.vercel-surface",
        scope=DEMO_SCOPE,
    )
    return registry, audit, Executor(registry, audit)


def run_demo(arguments: Any) -> dict[str, Any]:
    """Run one dry-run demonstration. Raises DemoError on refusal."""
    if not isinstance(arguments, Mapping):
        raise DemoError("request body must be a JSON object")
    unknown = sorted(set(arguments) - {"message", "dry_run"})
    if unknown:
        raise DemoError(f"unrecognised fields: {unknown}")
    if "dry_run" in arguments and arguments["dry_run"] is not True:
        raise DemoError(
            "dry_run is not negotiable on this surface: "
            "every run here is a dry run"
        )
    message = arguments.get("message", "")
    if not isinstance(message, str):
        raise DemoError("message must be a string")
    if len(message) > MAX_DEMO_MESSAGE_CHARS:
        raise DemoError(
            f"message exceeds {MAX_DEMO_MESSAGE_CHARS} characters"
        )
    _, audit, executor = build_demo()
    result = executor.execute(
        TaskRequest(
            task_id="vercel-demo",
            agent_id=DEMO_AGENT,
            tool_name=DEMO_TOOL,
            capability=DEMO_CAPABILITY,
            arguments={"message": message},
            scope=DEMO_SCOPE,
            dry_run=True,
        )
    )
    return {
        "status": result.status,
        "detail": result.detail,
        "dry_run": True,
        "tool_invoked": False,
        "audit_events_recorded": audit.count(),
    }


# -- HTTP plumbing --------------------------------------------------------


Responder = Callable[[str, Optional[bytes]], tuple[int, dict[str, Any]]]


def serve(http: BaseHTTPRequestHandler, responder: Responder) -> None:
    """Serve one request on a ``BaseHTTPRequestHandler`` instance.

    The entrypoint modules define the top-level ``handler`` class the
    Vercel Python runtime requires — its static analysis insists the
    name be defined in the entrypoint file itself — and delegate the
    actual work here, around a plain ``responder(method, body) ->
    (status, payload)`` function, so the logic stays testable without
    HTTP.
    """
    length = int(http.headers.get("Content-Length") or 0)
    body = http.rfile.read(length) if length else None
    status, payload = responder(http.command, body)
    data = json.dumps(payload, sort_keys=True).encode("utf-8")
    http.send_response(status)
    http.send_header("Content-Type", "application/json; charset=utf-8")
    http.send_header("Content-Length", str(len(data)))
    http.end_headers()
    if http.command != "HEAD":
        http.wfile.write(data)
