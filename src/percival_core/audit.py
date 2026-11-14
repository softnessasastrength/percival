"""Structured, redacted, append-only audit events for Percival Core.

The audit log is the durable record required by ADR-003 ("All external side
effects require scoped, logged user authorization") and by the M5 milestone
in DECISIONS.md ("structured redacted audit events"). It is local-first:
events are stored in a SQLite database on the host, using only the Python
standard library.

Every event detail passes through :func:`redact` before storage, so secrets
that slip into a payload (values under sensitive keys, bearer tokens, common
API-key shapes) are masked rather than persisted. Redaction is a safety net,
not a licence to log secrets deliberately.
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

REDACTED = "[redacted]"

_SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "authorization",
        "cookie",
        "password",
        "passwd",
        "private_key",
        "secret",
        "token",
    }
)

_SECRET_PATTERNS = (
    re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"\bsk-[A-Za-z0-9]{8,}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{8,}\b"),
    re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
)


def _mask_text(text: str) -> str:
    masked = text
    for pattern in _SECRET_PATTERNS:
        if pattern.groups:
            masked = pattern.sub(lambda m: f"{m.group(1)} {REDACTED}", masked)
        else:
            masked = pattern.sub(REDACTED, masked)
    return masked


def redact(value: Any) -> Any:
    """Return a copy of *value* with secrets masked.

    Mappings: values whose key looks sensitive are replaced wholesale.
    Strings: known secret shapes are masked inline. Other values pass
    through unchanged. The input is never mutated.
    """
    if isinstance(value, Mapping):
        return {
            key: REDACTED
            if isinstance(key, str) and key.lower() in _SENSITIVE_KEYS
            else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return _mask_text(value)
    return value


@dataclass(frozen=True)
class AuditEvent:
    """One immutable audit record."""

    id: int
    timestamp: str  # ISO 8601, UTC
    actor: str  # agent or principal that acted
    action: str  # dotted verb, e.g. "task.completed"
    outcome: str  # e.g. "allowed", "denied", "completed", "failed"
    detail: Mapping[str, Any]


class AuditLog:
    """Append-only audit log backed by a local SQLite database.

    ``path`` may be a filesystem path or ``":memory:"`` for tests. Events
    are never updated or deleted through this API.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = str(path)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                actor TEXT NOT NULL,
                action TEXT NOT NULL,
                outcome TEXT NOT NULL,
                detail TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def record(
        self,
        actor: str,
        action: str,
        outcome: str,
        detail: Optional[Mapping[str, Any]] = None,
    ) -> AuditEvent:
        """Append an event, redacting its detail payload before storage."""
        safe_detail = redact(dict(detail or {}))
        timestamp = datetime.now(timezone.utc).isoformat()
        with self._lock:
            cursor = self._conn.execute(
                "INSERT INTO audit_events (timestamp, actor, action, outcome, detail)"
                " VALUES (?, ?, ?, ?, ?)",
                (timestamp, actor, action, outcome, json.dumps(safe_detail, sort_keys=True)),
            )
            self._conn.commit()
            event_id = int(cursor.lastrowid)
        return AuditEvent(event_id, timestamp, actor, action, outcome, safe_detail)

    def events(self, action: Optional[str] = None) -> list[AuditEvent]:
        """Return events in insertion order, optionally filtered by action."""
        query = "SELECT id, timestamp, actor, action, outcome, detail FROM audit_events"
        params: tuple[Any, ...] = ()
        if action is not None:
            query += " WHERE action = ?"
            params = (action,)
        query += " ORDER BY id ASC"
        with self._lock:
            rows = self._conn.execute(query, params).fetchall()
        return [
            AuditEvent(
                id=row[0],
                timestamp=row[1],
                actor=row[2],
                action=row[3],
                outcome=row[4],
                detail=json.loads(row[5]),
            )
            for row in rows
        ]

    def count(self) -> int:
        with self._lock:
            return int(self._conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0])

    def close(self) -> None:
        with self._lock:
            self._conn.close()
