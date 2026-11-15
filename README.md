# Percival

A local-first personal operations steward for ZeroCloud. Percival coordinates planning, mobility, scheduling, and specialist agents while preserving human authority.

## Status

M0 bootstrap in progress. No external booking, spending, messaging, or calendar changes are implemented.

## Run locally (macOS/Linux)

The web surface — the front door plus the `/api/health` and `/api/demo`
endpoints — runs on your own machine with the Python standard library
alone (Python 3.11+; there are no dependencies to install):

```sh
python3 scripts/run_local.py
```

Then open <http://127.0.0.1:8123>. For a different port:
`python3 scripts/run_local.py --port 8200`. Stop with Control-C. The
runner binds loopback only and serves the same handler code as the
hosted deployment. The demo endpoint is dry-run only — it rejects any
request that asks otherwise — and no external actions exist on this
surface: nothing is sent, booked, or spent.

## Principles

- Truth before theatricality: never claim an action succeeded without evidence.
- Local-first, auditable, and privacy-conscious.
- Human approval for external side effects.
- Deterministic simulations before live integrations.
- The British butler personality is a presentation layer, not a permission system.

See `AGENTS.md`, `ROADMAP.md`, and `DECISIONS.md`.
