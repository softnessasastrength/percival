"""Percival Core foundation layer.

A framework-neutral, standard-library-only foundation implementing the
first slice of the M5 tool-execution milestone recorded in DECISIONS.md:

- :class:`~percival_core.registry.ToolRegistry` — deny-by-default typed
  tool registry with agent identities and per-tool capability grants.
- :class:`~percival_core.audit.AuditLog` — structured, redacted,
  append-only audit events in local SQLite.
- :class:`~percival_core.executor.Executor` — deterministic, bounded,
  dry-run-first task execution with graceful degradation.
- :mod:`percival_core.bring_to_me` — the F-001 feasibility core:
  three-state round-trip visit assessment ("come to me" / "go to
  them") against the Transit Atlas, plus draft-only outreach text.
  It performs no external side effect and contains no send path.

No external side effects are implemented here, and nothing in this
package grants itself authority: grants are issued by a host or
principal, in code, and every decision is auditable.
"""

from .audit import AuditEvent, AuditLog, redact
from .bring_to_me import (
    FEASIBLE,
    INNER_TIER,
    NOT_FEASIBLE,
    UNKNOWN,
    AtlasClient,
    AtlasError,
    AtlasRequestError,
    AtlasUnavailable,
    FriendRef,
    HomeRef,
    NotInnerTierError,
    assess_visit,
    draft_outreach,
)
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
    "FEASIBLE",
    "INNER_TIER",
    "NOT_FEASIBLE",
    "UNKNOWN",
    "AgentIdentity",
    "AtlasClient",
    "AtlasError",
    "AtlasRequestError",
    "AtlasUnavailable",
    "AuditEvent",
    "AuditLog",
    "CapabilityGrant",
    "Decision",
    "Executor",
    "FriendRef",
    "HomeRef",
    "NotInnerTierError",
    "TaskRequest",
    "TaskResult",
    "ToolRegistry",
    "ToolSpec",
    "ToolUnavailable",
    "assess_visit",
    "draft_outreach",
    "redact",
    "__version__",
]
