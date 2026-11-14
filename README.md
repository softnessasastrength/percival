# Percival

A local-first personal operations steward for ZeroCloud. Percival coordinates planning, mobility, scheduling, and specialist agents while preserving human authority.

## Status

M0 bootstrap in progress. No external booking, spending, messaging, or calendar changes are implemented.

## Principles

- Truth before theatricality: never claim an action succeeded without evidence.
- Local-first, auditable, and privacy-conscious.
- Human approval for external side effects.
- Deterministic simulations before live integrations.
- The British butler personality is a presentation layer, not a permission system.

See `AGENTS.md`, `ROADMAP.md`, and `DECISIONS.md`.

## Local terminal model profiles

Follow the [Mac mini smoke test](docs/smoke-test-macos.md) for setup. Use
`python -m percival models` to see the tags advertised by the local Ollama
server. Run `python -m percival chat` for Percival or
`python -m percival chat --agent coding` for the coding profile.

Edit [models.yaml](percival/models.yaml) or pass `chat --config PATH` to
load a custom registry. It maps agent profiles to an ordered list of installed
Ollama tags and sets each model's context and output limits. Each profile
loads a Markdown instructions file relative to the registry. The fallback
receives the same instructions and successful conversation history as the
primary. A single `--model TAG` overrides the profile's entire model list.

Set `--reasoning off|on|default` to override a profile's reasoning preference.
Quote `"off"` and `"on"` in YAML. When a model requires thinking, Percival
lets Ollama separate the trace and displays the final answer. It discards
structured thinking, recognized inline thinking tags, and replies cut off
at the output limit. Unmarked text that Ollama returns as a complete final
answer cannot be reliably distinguished from reasoning.

Chat skips candidates missing at startup and tries the next installed
candidate when a model call fails or produces no usable reply. Requests
stay on loopback and use explicit local Ollama references. Install models
before starting a session. Chat history is held in memory for the session.
