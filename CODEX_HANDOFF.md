# Codex Handoff — Percival Core

**Session:** 2026-11-14, Muse (Ember) engineering session under Branden's
written Muse Engineering Handoff, Priority B (Percival Core), while Codex
usage limits reset.
**Branch:** `percival-core-foundation_muse`; **PR #6** into `main`.

**Status update (owner decision, 2026-11-14; ADR-006 in DECISIONS.md):**
Branden adopted PR #6 as the **Percival Core foundation seed**, and it
merges into `main` as the adopted base. Codex builds forward from this
seed: harden and extend it; do not restart the foundation from scratch.

**Operating principle applied (owner, 2026-11-14):** Ember takes the small
things; Codex is reserved for the big stuff. The code was therefore built
as a small, tested, standard-library-only foundation slice rather than a
finished subsystem. With the owner's adoption (ADR-006) it is now the
**ADOPTED foundation seed**: this is the base Codex builds on. The
production identity-registry / task-execution subsystem remains Codex
work, built forward from this seed per the scoped tasks below.

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

Re-verified 2026-11-14 immediately before the adoption merge (ADR-006):
the local tree was confirmed byte-identical to the PR branch head for
all foundation files; `python3 -m unittest discover -s tests` → 24
tests ran, OK; `python3 -m compileall -q src tests` → OK.

Known honest limits:

- Executor timeouts abandon the worker thread; a handler that ignores
  abandonment may finish in the background. Handlers must be safe to
  abandon (stated in the module docstring).
- Redaction masks known key names and secret shapes; it is a safety net,
  not a guarantee. Do not log secrets deliberately.
- Grants/identities are in-memory; persistence is future work (below).

## Small-wins inventory (Ember, this session)

Done and verified end-to-end:

- **Repository truth audit.** The brief assumed a FastAPI + SQLite
  implementation; none exists. Verified from the tree itself and recorded
  here and in PR #6, so no further work is planned against phantom code.
- **Six-area evidence assessment** (below, and in PR #6): all six areas
  absent as code; permissions present only as prose policy.
- **Tested implementation** of the M5 foundation slice
  (registry / audit / executor, 24 passing tests) on this branch —
  adopted by the owner as the Percival Core foundation seed (ADR-006,
  2026-11-14) and merged to `main`.
- **This handoff document**, including reproducible verification commands.

Not done during the seed session, deliberately: any merge of the
feature code (see operating principle above); any change to existing
files (none needed; no bugs were reproducible in a documentation-only
tree). The merge itself happened afterwards, on 2026-11-14, under the
owner's explicit adoption decision (ADR-006).

## Scoped tasks for Codex (the big stuff)

1. **Identity registry & task-execution subsystem (M5 foundation).**
   Build the production design forward from the adopted seed now in
   `main` (PR #6, ADR-006): `ToolRegistry` semantics (deny-by-default,
   scoped, expiring, revocable grants), `AuditLog` event schema,
   `Executor` bounds and degradation contract. Harden and extend the
   seed — including its three carried-forward limitations
   (thread-abandonment timeout semantics; redaction as a safety net,
   not a guarantee; in-memory grants) — rather than restarting from
   scratch. Keep the 24-test behavioural contract or explicitly
   supersede it.
2. **Persistent mission ledger** (ROADMAP M0): SQLite-backed mission
   store alongside the audit log, so identities, grants, and mission
   states survive restarts. Includes the persistence design for grants
   (issuance/revocation history) that the adopted seed
   leaves in memory.
3. **Service boundary + explicit permission policy** (ROADMAP M0): a
   thin local service (FastAPI or stdlib HTTP — an open decision;
   ADR-001 keeps the core framework-neutral) exposing execution with
   dry-run as the default mode and ADR-003 authorization enforced at
   the boundary.
4. **Local model adapter (Qwen/Ollama)**: a tool whose handler calls a
   local Ollama endpoint and raises `ToolUnavailable` when it is down —
   the degradation path is already implemented and tested in the
   adopted seed; the adapter itself is not.
5. **OpenClaw workspace skill** with validated install instructions
   (ROADMAP M0), tested against a pinned OpenClaw version.
6. **M1 butler dispatch**: mission intake and bounded delegation on top
   of the foundation, with the deterministic synthetic mission tests
   the roadmap requires.

## Six-area assessment (evidence)

| Area | State | Evidence |
| --- | --- | --- |
| Permissions & explicit authorization | Prose only | `AGENTS.md` contract; ADR-003; no code existed |
| Agent/clanker identity registry | Absent on arrival | No code existed; adopted seed now in `main` (PR #6, ADR-006) |
| Deterministic task execution | Absent on arrival | No code existed; ROADMAP M1 unchecked; adopted seed in `main` (PR #6, ADR-006) |
| Audit logging | Absent on arrival | No code existed; ADR-003 requires it; adopted seed in `main` (PR #6, ADR-006) |
| Local Qwen/Ollama integration | Absent | No references in tree; ADR-002 discusses inference workers only |
| Graceful degradation | Absent on arrival | No code existed; `ToolUnavailable` path in adopted seed |

## Notes for the next engineer

- Repo policy (`AGENTS.md`, ADR-005) allows the active assistant to merge
  documentation and sandbox-verified bounded features via PR; material
  architecture/security-boundary changes, spending, deployment, and
  destructive operations still require Branden's fresh approval.
- Do not claim hardware or OpenClaw compatibility without testing on the
  target; sandbox success is sandbox success.
- The British-butler personality is a presentation layer only; keep it
  out of permission logic.
