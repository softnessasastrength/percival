# Codex Handoff — Percival Core

**Session:** 2026-11-14, Muse (Ember) engineering session under Branden's
written Muse Engineering Handoff, Priority B (Percival Core), while Codex
usage limits reset.
**Branch:** `percival-core-foundation_muse` (PR into `main`; no direct
pushes to `main`, nothing force-pushed).

## State of the repository on arrival

The repository contained **documentation only** — `README.md`,
`AGENTS.md`, `ROADMAP.md`, `DECISIONS.md`, and
`docs/architecture/openclaw.md`. There was no code, no test suite, and no
FastAPI or SQLite implementation anywhere in the tree, despite those being
mentioned in the session brief. All six evaluation areas from the brief
(permissions, identity registry, deterministic execution, audit logging,
local model integration, graceful degradation) were **absent as code**;
permissions and authorization existed only as prose policy (`AGENTS.md`,
ADR-003).

## What this change adds

The first, smallest slice of the **M5 tool-execution foundation** that
DECISIONS.md (ADR-005) names as the next bounded milestone: "a
deny-by-default typed registry, per-tool capability grants, bounded
time/output, structured redacted audit events, and a synthetic test
harness." Standard library only; framework-neutral, per ADR-001.

- `src/percival_core/registry.py` — `ToolRegistry`: agent ("clanker")
  identities, typed `ToolSpec`s, and narrow `CapabilityGrant`s (one
  agent, one tool, explicit capability subset, optional scope and
  expiry, revocable). `check()` is deny-by-default with stated reasons.
- `src/percival_core/audit.py` — `AuditLog`: append-only structured
  events in local SQLite, with redaction of sensitive keys and common
  secret shapes before storage.
- `src/percival_core/executor.py` — `Executor`: authorization first,
  dry-run by default (a dry run never claims an action happened),
  bounded output and timeouts, `ToolUnavailable` → graceful `degraded`
  result, every outcome audited. Deterministic: no randomness, no model
  calls.
- `tests/test_foundation.py` — 24 synthetic tests (unittest, stdlib).
- `pyproject.toml` — packaging metadata; zero dependencies.

No existing file was modified. No external side effects, network calls,
credentials, or model integrations are introduced. Nothing here grants
authority: grants are issued by a host/principal in code, and cloud or
local models remain unable to authorize anything.

## Reproduce / verify

```bash
python3 -m unittest discover -s tests -v   # 24 tests, all passing
python3 -m compileall -q src tests
```

Verified 2026-11-14 in Muse's Linux sandbox: Python 3.12.3,
SQLite 3.45.1. pytest is not installed in that sandbox; the suite is
deliberately stdlib-unittest so it runs anywhere, and also runs under
pytest unchanged.

Known honest limits:

- Executor timeouts abandon the worker thread; a handler that ignores
  abandonment may finish in the background. Handlers must be safe to
  abandon (stated in the module docstring).
- Redaction masks known key names and secret shapes; it is a safety net,
  not a guarantee. Do not log secrets deliberately.
- Grants/identities are in-memory; persistence is future work (below).

## Outstanding work (in recommended order)

1. **Persistent mission ledger** (ROADMAP M0): SQLite-backed mission
   store alongside the audit log, so identities, grants, and mission
   states survive restarts.
2. **Explicit permission policy + dry-run mode at the service boundary**
   (ROADMAP M0): a thin local service (FastAPI or stdlib HTTP — undecided;
   ADR-001 keeps the core framework-neutral) exposing the executor with
   dry-run as the default mode.
3. **Local model adapter (Qwen/Ollama)**: a tool whose handler calls a
   local Ollama endpoint and raises `ToolUnavailable` when it is down —
   the degradation path is already implemented and tested; the adapter
   itself is not.
4. **OpenClaw workspace skill** with validated install instructions
   (ROADMAP M0), tested against a pinned OpenClaw version.
5. **M1 butler dispatch**: mission intake and bounded delegation on top
   of this foundation, with the deterministic synthetic mission tests
   the roadmap requires.

## Notes for the next engineer

- Repo policy (`AGENTS.md`, ADR-005) allows the active assistant to merge
  documentation and sandbox-verified bounded features via PR; material
  architecture/security-boundary changes, spending, deployment, and
  destructive operations still require Branden's fresh approval.
- Do not claim hardware or OpenClaw compatibility without testing on the
  target; sandbox success is sandbox success.
- The British-butler personality is a presentation layer only; keep it
  out of permission logic.
