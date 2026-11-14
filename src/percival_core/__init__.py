"""Percival Core foundation layer.

A framework-neutral, standard-library-only foundation implementing the
first slice of the M5 tool-execution milestone recorded in DECISIONS.md:

- :class:`~percival_core.registry.ToolRegistry` — deny-by-default typed
  tool registry with agent identities and per-tool capability grants.
- :class:`~percival_core.audit.AuditLog` — structured, redacted,
  append-only audit events in local SQLite.
- :class:`~percival_core.executor.Executor` — deterministic, bounded,
  dry-run-first task execution with graceful degradation.

No external side effects are implemented here, and nothing in this
package grants itself authority: grants are issued by a host or
principal, in code, and every decision is auditable.
"""

from .audit import AuditEvent, AuditLog, redact
from .executor import (
    Executor,
    TaskRequest,
    TaskResult,
    ToolUnavailable,
)
from .registry import (
    AgentIdentity,
    CapabilityGrant,
    Decision,
    ToolRegistry,
    ToolSpec,
)

__version__ = "0.1.0"

__all__ = [
    "AgentIdentity",
    "AuditEvent",
    "AuditLog",
    "CapabilityGrant",
    "Decision",
    "Executor",
    "TaskRequest",
    "TaskResult",
    "ToolRegistry",
    "ToolSpec",
    "ToolUnavailable",
    "redact",
    "__version__",
]
