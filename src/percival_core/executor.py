"""Deterministic, bounded, dry-run-first task executor.

The executor is the only path from an authorization decision to a tool
invocation in this foundation layer. Its guarantees:

- **Authorization first.** Every request is checked against the registry;
  a denial is final, is audited, and the tool is never invoked.
- **Dry-run by default.** Unless a request explicitly sets
  ``dry_run=False``, the tool is not invoked. A dry run reports whether
  the request *would* be permitted; it never claims an action happened
  (README: "Truth before theatricality").
- **Bounded.** Tool output is truncated to the tool's declared
  ``max_output_chars`` and execution is bounded by its
  ``timeout_seconds``. Note the honest limit of the timeout: it is
  enforced with a worker thread, so a timed-out call is *abandoned*, and
  a handler that ignores abandonment may still finish in the background.
  Handlers must therefore be safe to abandon.
- **Graceful degradation.** A handler that raises :class:`ToolUnavailable`
  (its model, service, or device is unreachable) yields a ``degraded``
  result with a plain explanation instead of an unhandled exception, so
  the steward can report reduced service rather than fail outright.
- **Audited.** Every request outcome — denied, dry-run, completed,
  failed, degraded, timed out — is written to the audit log.
- **Deterministic.** Given the same registry state and a deterministic
  handler, the same request produces the same status and output. The
  executor adds no randomness, no wall-clock-dependent branching, and no
  model calls of its own.
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from typing import Any, Mapping

from .audit import AuditLog
from .registry import ToolRegistry

STATUS_COMPLETED = "completed"
STATUS_DRY_RUN = "dry_run"
STATUS_DENIED = "denied"
STATUS_FAILED = "failed"
STATUS_DEGRADED = "degraded"
STATUS_TIMEOUT = "timeout"


class ToolUnavailable(Exception):
    """Raised by a tool handler when its backend (model, service, or
    device) is unavailable. The executor converts this into a degraded
    result rather than a failure."""


@dataclass(frozen=True)
class TaskRequest:
    """One bounded request for a tool invocation."""

    task_id: str
    agent_id: str
    tool_name: str
    capability: str
    arguments: Mapping[str, Any]
    scope: str = ""
    dry_run: bool = True


@dataclass(frozen=True)
class TaskResult:
    """The verified outcome of a request. ``output`` is empty unless the
    status is ``completed`` (or ``degraded`` with partial output)."""

    task_id: str
    status: str
    output: str = ""
    detail: str = ""
    duration_ms: int = 0


class Executor:
    """Executes task requests against a registry, with an audit trail."""

    def __init__(self, registry: ToolRegistry, audit: AuditLog) -> None:
        self._registry = registry
        self._audit = audit

    def execute(self, request: TaskRequest) -> TaskResult:
        started = time.monotonic()
        decision = self._registry.check(
            request.agent_id, request.tool_name, request.capability, request.scope
        )
        if not decision.allowed:
            result = TaskResult(
                task_id=request.task_id,
                status=STATUS_DENIED,
                detail=decision.reason,
                duration_ms=self._elapsed_ms(started),
            )
            self._record(request, "authorization.denied", result)
            return result

        spec = self._registry.tool(request.tool_name)
        assert spec is not None  # guaranteed by the successful check

        if request.dry_run:
            result = TaskResult(
                task_id=request.task_id,
                status=STATUS_DRY_RUN,
                detail=(
                    "Dry run: the tool was not invoked. Authorization would "
                    f"permit '{request.capability}' on '{request.tool_name}'."
                ),
                duration_ms=self._elapsed_ms(started),
            )
            self._record(request, "task.dry_run", result)
            return result

        try:
            raw = self._invoke_with_timeout(spec, request.arguments)
        except ToolUnavailable as exc:
            result = TaskResult(
                task_id=request.task_id,
                status=STATUS_DEGRADED,
                detail=f"Tool backend unavailable: {exc}",
                duration_ms=self._elapsed_ms(started),
            )
            self._record(request, "task.degraded", result)
            return result
        except FutureTimeoutError:
            result = TaskResult(
                task_id=request.task_id,
                status=STATUS_TIMEOUT,
                detail=(
                    f"Tool '{spec.name}' exceeded its bound of "
                    f"{spec.timeout_seconds} seconds and was abandoned."
                ),
                duration_ms=self._elapsed_ms(started),
            )
            self._record(request, "task.timeout", result)
            return result
        except Exception as exc:  # handler failure: report type, never hide it
            result = TaskResult(
                task_id=request.task_id,
                status=STATUS_FAILED,
                detail=f"Tool raised {type(exc).__name__}: {exc}",
                duration_ms=self._elapsed_ms(started),
            )
            self._record(request, "task.failed", result)
            return result

        output = raw if isinstance(raw, str) else json.dumps(raw, sort_keys=True, default=str)
        detail = ""
        if len(output) > spec.max_output_chars:
            output = output[: spec.max_output_chars]
            detail = f"Output truncated to {spec.max_output_chars} characters."
        result = TaskResult(
            task_id=request.task_id,
            status=STATUS_COMPLETED,
            output=output,
            detail=detail,
            duration_ms=self._elapsed_ms(started),
        )
        self._record(request, "task.completed", result)
        return result

    # -- internals ------------------------------------------------------

    @staticmethod
    def _invoke_with_timeout(spec, arguments: Mapping[str, Any]) -> Any:
        pool = ThreadPoolExecutor(max_workers=1)
        try:
            future = pool.submit(spec.handler, arguments)
            return future.result(timeout=spec.timeout_seconds)
        finally:
            # Do not wait for an abandoned call; handlers must be safe to
            # abandon (see module docstring).
            pool.shutdown(wait=False)

    @staticmethod
    def _elapsed_ms(started: float) -> int:
        return int((time.monotonic() - started) * 1000)

    def _record(self, request: TaskRequest, action: str, result: TaskResult) -> None:
        self._audit.record(
            request.agent_id,
            action,
            result.status,
            {
                "task_id": request.task_id,
                "tool": request.tool_name,
                "capability": request.capability,
                "scope": request.scope,
                "dry_run": request.dry_run,
                "detail": result.detail,
            },
        )
