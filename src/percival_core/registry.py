"""Deny-by-default typed tool registry with per-agent capability grants.

This module implements the enforcement half of the Percival agent contract:
"Delegate narrow tasks to specialist agents; enforce permissions in code,
not in prose" (AGENTS.md) and ADR-003 ("No implicit external authority").

Design rules:

- **Deny by default.** An authorization check succeeds only when a known
  agent holds an active grant covering the exact tool, capability, and
  scope requested. Every other case denies, with a stated reason.
- **Identity before authority.** Agents ("clankers") must be registered
  with an identity before they can hold grants or pass a check.
- **Grants are narrow.** A grant names one agent, one tool, an explicit
  set of capabilities (a subset of the tool's declared capabilities), an
  optional scope string, and an optional expiry. Grants are issued by a
  named grantor and can be revoked.
- **Models do not grant.** Nothing in this module lets a tool or an agent
  create its own grant; issuance is a host/principal action, recorded in
  the audit log when one is attached.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Optional

from .audit import AuditLog

DEFAULT_MAX_OUTPUT_CHARS = 4096
DEFAULT_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class AgentIdentity:
    """A registered specialist agent (a "clanker") known to the core."""

    agent_id: str
    display_name: str
    description: str = ""


@dataclass(frozen=True)
class ToolSpec:
    """A typed tool declaration.

    ``capabilities`` names the distinct powers the tool exposes; a grant
    may cover only a subset. ``side_effects`` marks tools that change the
    world beyond Percival (sending, booking, spending); the executor
    treats dry-run as the default for every tool regardless, and hosts
    should require explicit, scoped user authorization before a live
    side-effecting call, per ADR-003.
    """

    name: str
    description: str
    capabilities: frozenset[str]
    handler: Callable[[Mapping[str, Any]], Any]
    side_effects: bool = False
    max_output_chars: int = DEFAULT_MAX_OUTPUT_CHARS
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS


@dataclass(frozen=True)
class CapabilityGrant:
    """A narrow, revocable grant of specific capabilities to one agent."""

    grant_id: str
    agent_id: str
    tool_name: str
    capabilities: frozenset[str]
    granted_by: str
    scope: str = ""
    expires_at: Optional[datetime] = None

    def is_active(self, now: datetime) -> bool:
        return self.expires_at is None or now < self.expires_at


@dataclass(frozen=True)
class Decision:
    """The outcome of an authorization check, with a human-readable reason."""

    allowed: bool
    reason: str


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ToolRegistry:
    """Registry of agent identities, tool specifications, and grants."""

    def __init__(self, audit: Optional[AuditLog] = None) -> None:
        self._audit = audit
        self._agents: dict[str, AgentIdentity] = {}
        self._tools: dict[str, ToolSpec] = {}
        self._grants: dict[str, CapabilityGrant] = {}
        self._revoked: set[str] = set()

    # -- identities -----------------------------------------------------

    def register_agent(
        self, agent_id: str, display_name: str, description: str = ""
    ) -> AgentIdentity:
        if agent_id in self._agents:
            raise ValueError(f"agent already registered: {agent_id}")
        identity = AgentIdentity(agent_id, display_name, description)
        self._agents[agent_id] = identity
        self._log("percival.core", "agent.registered", "recorded", {"agent_id": agent_id})
        return identity

    def agent(self, agent_id: str) -> Optional[AgentIdentity]:
        return self._agents.get(agent_id)

    # -- tools ----------------------------------------------------------

    def register_tool(self, spec: ToolSpec) -> ToolSpec:
        if spec.name in self._tools:
            raise ValueError(f"tool already registered: {spec.name}")
        if not spec.capabilities:
            raise ValueError(f"tool {spec.name} declares no capabilities")
        self._tools[spec.name] = spec
        self._log(
            "percival.core",
            "tool.registered",
            "recorded",
            {"tool": spec.name, "side_effects": spec.side_effects},
        )
        return spec

    def tool(self, name: str) -> Optional[ToolSpec]:
        return self._tools.get(name)

    # -- grants ---------------------------------------------------------

    def grant(
        self,
        agent_id: str,
        tool_name: str,
        capabilities: set[str] | frozenset[str],
        granted_by: str,
        scope: str = "",
        expires_at: Optional[datetime] = None,
    ) -> CapabilityGrant:
        """Issue a grant. Raises ValueError for unknown agent/tool or for
        capabilities the tool does not declare."""
        if agent_id not in self._agents:
            raise ValueError(f"unknown agent: {agent_id}")
        spec = self._tools.get(tool_name)
        if spec is None:
            raise ValueError(f"unknown tool: {tool_name}")
        requested = frozenset(capabilities)
        if not requested:
            raise ValueError("a grant must name at least one capability")
        if not requested <= spec.capabilities:
            extra = sorted(requested - spec.capabilities)
            raise ValueError(f"capabilities not declared by tool {tool_name}: {extra}")
        grant = CapabilityGrant(
            grant_id=uuid.uuid4().hex,
            agent_id=agent_id,
            tool_name=tool_name,
            capabilities=requested,
            granted_by=granted_by,
            scope=scope,
            expires_at=expires_at,
        )
        self._grants[grant.grant_id] = grant
        self._log(
            granted_by,
            "grant.issued",
            "recorded",
            {
                "grant_id": grant.grant_id,
                "agent_id": agent_id,
                "tool": tool_name,
                "capabilities": sorted(requested),
                "scope": scope,
            },
        )
        return grant

    def revoke(self, grant_id: str, revoked_by: str) -> bool:
        """Revoke a grant. Returns False if the grant is unknown or
        already revoked."""
        if grant_id not in self._grants or grant_id in self._revoked:
            return False
        self._revoked.add(grant_id)
        grant = self._grants[grant_id]
        self._log(
            revoked_by,
            "grant.revoked",
            "recorded",
            {"grant_id": grant_id, "agent_id": grant.agent_id, "tool": grant.tool_name},
        )
        return True

    # -- authorization --------------------------------------------------

    def check(
        self,
        agent_id: str,
        tool_name: str,
        capability: str,
        scope: str = "",
        now: Optional[datetime] = None,
    ) -> Decision:
        """Deny-by-default authorization check.

        Allows only when an active, unrevoked grant covers the exact
        agent, tool, capability, and scope. A grant with an empty scope
        covers any requested scope; a scoped grant covers only its own
        scope.
        """
        moment = now or _utcnow()
        if agent_id not in self._agents:
            return Decision(False, f"unknown agent: {agent_id}")
        spec = self._tools.get(tool_name)
        if spec is None:
            return Decision(False, f"unknown tool: {tool_name}")
        if capability not in spec.capabilities:
            return Decision(False, f"tool {tool_name} has no capability: {capability}")
        for grant in self._grants.values():
            if grant.grant_id in self._revoked:
                continue
            if grant.agent_id != agent_id or grant.tool_name != tool_name:
                continue
            if capability not in grant.capabilities:
                continue
            if grant.scope and grant.scope != scope:
                continue
            if not grant.is_active(moment):
                continue
            return Decision(True, f"allowed by grant {grant.grant_id}")
        return Decision(
            False,
            f"no active grant covers agent={agent_id} tool={tool_name}"
            f" capability={capability} scope={scope!r}",
        )

    # -- internals ------------------------------------------------------

    def _log(
        self, actor: str, action: str, outcome: str, detail: Mapping[str, Any]
    ) -> None:
        if self._audit is not None:
            self._audit.record(actor, action, outcome, detail)
