"""Synthetic tests for the Percival Core foundation layer.

Run with either:
    python3 -m unittest discover -s tests -v
    python3 -m pytest            (if pytest is available)

All fixtures are synthetic; no real user data, credentials, or external
services are involved.
"""

from __future__ import annotations

import sys
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from percival_core import (  # noqa: E402
    AuditLog,
    Executor,
    TaskRequest,
    ToolRegistry,
    ToolSpec,
    ToolUnavailable,
    redact,
)


def _echo(arguments):
    return f"echo:{arguments.get('text', '')}"


def _unavailable(arguments):
    raise ToolUnavailable("local model endpoint did not respond")


def _boom(arguments):
    raise RuntimeError("synthetic failure")


def _slow(arguments):
    time.sleep(2.0)
    return "too late"


def _loud(arguments):
    return "x" * 100


class AuditLogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.log = AuditLog(":memory:")

    def tearDown(self) -> None:
        self.log.close()

    def test_record_and_read_back_in_order(self) -> None:
        self.log.record("agent.a", "task.completed", "completed", {"task_id": "t1"})
        self.log.record("agent.a", "task.failed", "failed", {"task_id": "t2"})
        events = self.log.events()
        self.assertEqual([e.action for e in events], ["task.completed", "task.failed"])
        self.assertEqual(events[0].detail["task_id"], "t1")
        self.assertEqual(self.log.count(), 2)

    def test_filter_by_action(self) -> None:
        self.log.record("agent.a", "grant.issued", "recorded", {})
        self.log.record("agent.a", "task.completed", "completed", {})
        self.assertEqual(len(self.log.events(action="grant.issued")), 1)

    def test_sensitive_keys_are_redacted(self) -> None:
        event = self.log.record(
            "agent.a",
            "task.completed",
            "completed",
            {"api_key": "skouldnotbeseen", "note": "fine"},
        )
        self.assertEqual(event.detail["api_key"], "[redacted]")
        self.assertEqual(event.detail["note"], "fine")
        stored = self.log.events()[0]
        self.assertEqual(stored.detail["api_key"], "[redacted]")

    def test_secret_shapes_masked_in_free_text(self) -> None:
        self.assertIn("[redacted]", redact("Authorization: Bearer abcdefgh12345678"))
        self.assertIn("[redacted]", redact("key sk-abcdefgh12345678 here"))
        self.assertEqual(redact("nothing secret"), "nothing secret")

    def test_redact_does_not_mutate_input(self) -> None:
        payload = {"token": "abc", "nested": {"count": 3}}
        redact(payload)
        self.assertEqual(payload["token"], "abc")


class RegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.audit = AuditLog(":memory:")
        self.registry = ToolRegistry(self.audit)
        self.registry.register_agent("clanker.echo", "Echo Clanker")
        self.registry.register_tool(
            ToolSpec(
                name="echo",
                description="Synthetic echo tool",
                capabilities=frozenset({"speak", "whisper"}),
                handler=_echo,
            )
        )

    def tearDown(self) -> None:
        self.audit.close()

    def test_unknown_agent_denied(self) -> None:
        decision = self.registry.check("ghost", "echo", "speak")
        self.assertFalse(decision.allowed)
        self.assertIn("unknown agent", decision.reason)

    def test_unknown_tool_denied(self) -> None:
        decision = self.registry.check("clanker.echo", "teleport", "speak")
        self.assertFalse(decision.allowed)
        self.assertIn("unknown tool", decision.reason)

    def test_no_grant_denied_by_default(self) -> None:
        decision = self.registry.check("clanker.echo", "echo", "speak")
        self.assertFalse(decision.allowed)
        self.assertIn("no active grant", decision.reason)

    def test_grant_allows_exact_capability_only(self) -> None:
        self.registry.grant("clanker.echo", "echo", {"speak"}, granted_by="principal")
        self.assertTrue(self.registry.check("clanker.echo", "echo", "speak").allowed)
        self.assertFalse(self.registry.check("clanker.echo", "echo", "whisper").allowed)

    def test_grant_cannot_exceed_tool_capabilities(self) -> None:
        with self.assertRaises(ValueError):
            self.registry.grant("clanker.echo", "echo", {"fly"}, granted_by="principal")

    def test_grant_for_unknown_agent_or_tool_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.registry.grant("ghost", "echo", {"speak"}, granted_by="principal")
        with self.assertRaises(ValueError):
            self.registry.grant("clanker.echo", "teleport", {"speak"}, granted_by="principal")

    def test_scoped_grant_matches_only_its_scope(self) -> None:
        self.registry.grant(
            "clanker.echo", "echo", {"speak"}, granted_by="principal", scope="household"
        )
        self.assertTrue(
            self.registry.check("clanker.echo", "echo", "speak", scope="household").allowed
        )
        self.assertFalse(
            self.registry.check("clanker.echo", "echo", "speak", scope="estate").allowed
        )

    def test_expired_grant_denied(self) -> None:
        past = datetime.now(timezone.utc) - timedelta(minutes=1)
        self.registry.grant(
            "clanker.echo", "echo", {"speak"}, granted_by="principal", expires_at=past
        )
        self.assertFalse(self.registry.check("clanker.echo", "echo", "speak").allowed)

    def test_revoked_grant_denied(self) -> None:
        grant = self.registry.grant(
            "clanker.echo", "echo", {"speak"}, granted_by="principal"
        )
        self.assertTrue(self.registry.check("clanker.echo", "echo", "speak").allowed)
        self.assertTrue(self.registry.revoke(grant.grant_id, revoked_by="principal"))
        self.assertFalse(self.registry.check("clanker.echo", "echo", "speak").allowed)
        self.assertFalse(self.registry.revoke(grant.grant_id, revoked_by="principal"))

    def test_duplicate_registration_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.registry.register_agent("clanker.echo", "Duplicate")
        with self.assertRaises(ValueError):
            self.registry.register_tool(
                ToolSpec("echo", "dup", frozenset({"speak"}), _echo)
            )

    def test_grants_and_revokes_are_audited(self) -> None:
        grant = self.registry.grant(
            "clanker.echo", "echo", {"speak"}, granted_by="principal"
        )
        self.registry.revoke(grant.grant_id, revoked_by="principal")
        actions = [e.action for e in self.audit.events()]
        self.assertIn("grant.issued", actions)
        self.assertIn("grant.revoked", actions)


class ExecutorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.audit = AuditLog(":memory:")
        self.registry = ToolRegistry(self.audit)
        self.registry.register_agent("clanker.echo", "Echo Clanker")
        self.registry.register_tool(
            ToolSpec("echo", "echo", frozenset({"speak"}), _echo)
        )
        self.registry.register_tool(
            ToolSpec("fragile", "backend down", frozenset({"ask"}), _unavailable)
        )
        self.registry.register_tool(
            ToolSpec("broken", "always raises", frozenset({"ask"}), _boom)
        )
        self.registry.register_tool(
            ToolSpec(
                "slow",
                "sleeps past its bound",
                frozenset({"ask"}),
                _slow,
                timeout_seconds=0.2,
            )
        )
        self.registry.register_tool(
            ToolSpec(
                "loud",
                "overlong output",
                frozenset({"shout"}),
                _loud,
                max_output_chars=10,
            )
        )
        for tool, cap in (
            ("echo", "speak"),
            ("fragile", "ask"),
            ("broken", "ask"),
            ("slow", "ask"),
            ("loud", "shout"),
        ):
            self.registry.grant("clanker.echo", tool, {cap}, granted_by="principal")
        self.executor = Executor(self.registry, self.audit)
        self.invocations: list[str] = []

    def tearDown(self) -> None:
        self.audit.close()

    def _request(self, tool: str, cap: str, dry_run: bool, task_id: str = "t") -> TaskRequest:
        return TaskRequest(
            task_id=task_id,
            agent_id="clanker.echo",
            tool_name=tool,
            capability=cap,
            arguments={"text": "good evening"},
            dry_run=dry_run,
        )

    def test_denied_request_never_invokes_and_is_audited(self) -> None:
        request = TaskRequest(
            task_id="t-denied",
            agent_id="clanker.echo",
            tool_name="echo",
            capability="whisper",  # not granted, and not even declared
            arguments={},
            dry_run=False,
        )
        result = self.executor.execute(request)
        self.assertEqual(result.status, "denied")
        self.assertEqual(result.output, "")
        denied = self.audit.events(action="authorization.denied")
        self.assertEqual(len(denied), 1)
        self.assertEqual(denied[0].detail["task_id"], "t-denied")

    def test_dry_run_does_not_invoke_handler(self) -> None:
        calls: list[str] = []

        def counting(arguments):
            calls.append("called")
            return "should not happen"

        audit = AuditLog(":memory:")
        registry = ToolRegistry(audit)
        registry.register_agent("a", "A")
        registry.register_tool(ToolSpec("count", "c", frozenset({"go"}), counting))
        registry.grant("a", "count", {"go"}, granted_by="principal")
        executor = Executor(registry, audit)
        result = executor.execute(
            TaskRequest("t-dry", "a", "count", "go", {}, dry_run=True)
        )
        self.assertEqual(result.status, "dry_run")
        self.assertEqual(calls, [])
        self.assertEqual(result.output, "")
        audit.close()

    def test_live_run_completes_with_output(self) -> None:
        result = self.executor.execute(self._request("echo", "speak", dry_run=False))
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.output, "echo:good evening")
        completed = self.audit.events(action="task.completed")
        self.assertEqual(len(completed), 1)

    def test_deterministic_repeat_runs(self) -> None:
        first = self.executor.execute(self._request("echo", "speak", dry_run=False, task_id="t1"))
        second = self.executor.execute(self._request("echo", "speak", dry_run=False, task_id="t2"))
        self.assertEqual(first.status, second.status)
        self.assertEqual(first.output, second.output)

    def test_unavailable_backend_degrades_gracefully(self) -> None:
        result = self.executor.execute(self._request("fragile", "ask", dry_run=False))
        self.assertEqual(result.status, "degraded")
        self.assertIn("unavailable", result.detail.lower())
        self.assertEqual(len(self.audit.events(action="task.degraded")), 1)

    def test_handler_exception_is_a_failure_not_a_crash(self) -> None:
        result = self.executor.execute(self._request("broken", "ask", dry_run=False))
        self.assertEqual(result.status, "failed")
        self.assertIn("RuntimeError", result.detail)

    def test_timeout_is_bounded(self) -> None:
        started = time.monotonic()
        result = self.executor.execute(self._request("slow", "ask", dry_run=False))
        elapsed = time.monotonic() - started
        self.assertEqual(result.status, "timeout")
        self.assertLess(elapsed, 1.5)

    def test_output_is_truncated_to_tool_bound(self) -> None:
        result = self.executor.execute(self._request("loud", "shout", dry_run=False))
        self.assertEqual(result.status, "completed")
        self.assertEqual(len(result.output), 10)
        self.assertIn("truncated", result.detail)


if __name__ == "__main__":
    unittest.main()
