# Architecture Decisions

## ADR-001: OpenClaw as optional host
Percival targets OpenClaw as its primary agent runtime and distribution surface, while retaining a framework-neutral mission core. Skills express repeatable procedures; plugins expose typed tools and integrations. Version-specific APIs must be verified against the installed OpenClaw release.

## ADR-002: One Gateway, many nodes
Prefer one trusted Gateway with separately paired device nodes for multi-Mac installations. Nodes provide remote capabilities, not automatic pooled inference. Separate inference workers require an explicit scheduler and backend.

## ADR-003: No implicit external authority
All external side effects require scoped, logged user authorization. Model instructions alone are not a security boundary.

## ADR-004: Public repository hygiene
Never commit real user schedules, contacts, addresses, API keys, tokens, or private mission logs. Synthetic examples only.
