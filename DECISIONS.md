# Architecture Decisions

## ADR-001: OpenClaw as optional host
Percival targets OpenClaw as its primary agent runtime and distribution surface, while retaining a framework-neutral mission core. Skills express repeatable procedures; plugins expose typed tools and integrations. Version-specific APIs must be verified against the installed OpenClaw release.

## ADR-002: One Gateway, many nodes
Prefer one trusted Gateway with separately paired device nodes for multi-Mac installations. Nodes provide remote capabilities, not automatic pooled inference. Separate inference workers require an explicit scheduler and backend.

## ADR-003: No implicit external authority
All external side effects require scoped, logged user authorization. Model instructions alone are not a security boundary.

## ADR-004: Public repository hygiene
Never commit real user schedules, contacts, addresses, API keys, tokens, or private mission logs. Synthetic examples only.

## ADR-005: Bounded contributor merge delegation (2026-11-14)
**Decision:** The repository owner delegates routine documentation merges and sandbox-verified, CI-checked bounded feature/test/fix merges to the active development assistant. This is a human-directed contribution policy, not a runtime privilege for Percival or its specialist agents.

**Evidence required:** inspect diff and dependencies, document tests executed and their environment, confirm applicable CI and branch protection requirements, and identify residual risks. Documentation-only changes require accuracy, privacy, and scope review. Keep changes small and auditable.

**Approval boundary:** ask the owner before material architecture or security-boundary changes, spending, deployment, destructive changes, or real-world external side effects. Do not weaken required checks to merge. Hardware claims require actual hardware validation.

**Operational limit:** authorization applies only while the assistant is actively executing an authorized task; no continuous autonomous service is established.

**Next bounded milestone:** M5 tool-execution foundation. First design and test a deny-by-default typed registry, per-tool capability grants, bounded time/output, structured redacted audit events, and a synthetic test harness. Command execution and filesystem access must be confined to explicit allowlists and isolated workspaces; do not silently grant host shell access. Escalate any proposed widening of security privileges for review.

## ADR-006: PR #6 adopted as the Percival Core foundation seed (2026-11-14)
**Decision:** The repository owner (Branden Algozino) adopted PR #6 — the tested implementation of the M5 tool-execution foundation slice (`src/percival_core/`: deny-by-default typed registry, redacted SQLite audit log, bounded dry-run-first executor; 24 stdlib tests) — as the **foundation seed** for Percival Core on 2026-11-14. It merges into `main` as the base Codex builds forward from: harden and extend the seed; do not restart the foundation from scratch.

**Pre-merge verification (2026-11-14, Muse Linux sandbox, Python 3.12.3):** the local tree was confirmed byte-identical to the PR branch head (`percival-core-foundation_muse` @ 7bc6cbb) for all foundation files; `python3 -m unittest discover -s tests` → 24 tests ran, OK; `python3 -m compileall -q src tests` → OK.

**Carried forward as Codex's hardening list** (known limitations of the seed, unchanged by adoption):
- Executor timeouts abandon the worker thread; a handler that ignores abandonment may finish in the background. Handlers must be safe to abandon.
- Audit redaction masks known key names and common secret shapes; it is a safety net, not a guarantee. Secrets must not be logged deliberately.
- Identities and capability grants are in-memory only; persistence (the mission ledger named in ADR-005) is future Codex work.
