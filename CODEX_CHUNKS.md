# Percival — Luna-sized Codex chunks

These chunks decompose the scoped Percival work in `CODEX_HANDOFF.md` and
`FEATURE_QUEUE_muse.md` into pieces a mid-tier coding model can complete in
one sitting without frontier-level design judgment. They are work orders,
not new architecture and not permission to widen Percival's authority.

## How to consume a chunk

1. Take the earliest chunk whose dependencies are complete. Do not combine
   chunks merely because they touch the same file.
2. Read the chunk card, the linked current code, `AGENTS.md`, and the
   relevant decisions in `DECISIONS.md` before editing.
3. Keep the implementation inside the listed files. Prefer the existing
   standard-library patterns: SQLite for local persistence, frozen
   dataclasses for records, explicit result objects, and synthetic
   `unittest` fixtures.
4. A chunk is **done** only when all of the following are true:
   - its acceptance test passes;
   - the full suite passes: `python3 -m unittest discover -s tests`;
   - compilation passes: `python3 -m compileall -q src tests api`;
   - a dated `DECISIONS.md` entry records the chunk ID, material design
     choices, tests run, environment, and any residual limit.
5. Use synthetic people, places, stops, messages, and credentials only
   (ADR-004). Tests must not require a real network, real account, real
   API key, or a running external service unless the existing live-Atlas
   test already governs that exception.

## Stop-and-report rule

Stop the chunk and report the blocker instead of improvising if:

- the acceptance test cannot be made concrete without changing an earlier
  chunk's contract;
- the work needs a file or subsystem outside the card's bounds;
- it needs a new dependency, credential, real personal data, real network
  integration, paid service, deployment, or external side effect;
- it would alter a permission, approval, privacy, or security boundary;
- an existing test fails for an unrelated reason; or
- the card's factual premise no longer matches the code.

The report should name the chunk, the exact failed premise, the evidence,
and the smallest decision needed from Ember or the owner. A stopped chunk
is useful information, not a failed sitting.

## Consumption order

P-01 → P-02 → P-03; P-04 → P-05; P-06; P-07 → P-08 → P-09; P-10 → P-11 →
P-12 → P-13 → P-14 → P-15; P-16; P-17 → P-18; P-19 → P-20; P-21 → P-22;
P-23. Independent branches may be taken in ID order when their listed
dependencies are met.

---

## Foundation hardening

### P-01 — Persistent registry store

**Objective:** Add a standalone SQLite `RegistryStore`, following
`AuditLog`'s local-file, locking, and JSON patterns. Persist agent
identities, capability grants, and revoked grant IDs. Tool handlers are
callables and must not be serialised; the store persists references and
grant data only.

**Files:** `src/percival_core/persistence.py` (new);
`tests/test_registry_persistence.py` (new).

**Acceptance:** With a temporary database, store one synthetic agent and
two grants, revoke one grant, close and reopen the store, and assert the
loaded identities, capabilities, scopes, expiries, grantor values, and
revocation state match exactly. Duplicate grant IDs are rejected and an
unknown schema version raises a named error. Run
`python3 -m unittest discover -s tests -p 'test_registry_persistence.py'`,
then the full suite.

**Depends on:** None.

### P-02 — Rehydrate `ToolRegistry` from the persistent store

**Objective:** Add optional store support to `ToolRegistry`. On startup it
loads identities, grants, and revocations from P-01; registration, grant,
and revocation write through to the store. Tool specs remain registered in
code by the host. Loading a grant for a not-yet-registered tool must not
invent the tool or its handler.

**Files:** `src/percival_core/persistence.py`;
`src/percival_core/registry.py`; `src/percival_core/__init__.py`;
`tests/test_registry_persistence.py`.

**Acceptance:** Register the same synthetic tool in two registries backed
by one temporary store file. A grant issued through the first allows the
check in the second; a revocation through the first denies it in the
second; expiry and scope behaviour match the in-memory registry. Run the
targeted persistence tests, then the full suite.

**Depends on:** P-01.

### P-03 — Append-only grant history

**Objective:** Record grant issuance and revocation as append-only events
in the persistent store and expose an ordered `history()` query filtered
optionally by agent or tool. Each event carries grant ID, actor, action,
timestamp, capability snapshot, and scope. Current grant state remains a
separate record; history is never updated or deleted through the API.

**Files:** `src/percival_core/persistence.py`;
`src/percival_core/registry.py`;
`tests/test_registry_persistence.py`.

**Acceptance:** Issue, revoke, and reissue a synthetic grant and assert
the reopened store returns exactly three history events in order with the
correct actors and capability snapshots. Assert there is no public update
or delete method for history. Run the targeted persistence tests, then
the full suite.

**Depends on:** P-02.

### P-04 — Cooperative cancellation for timed-out handlers

**Objective:** Add an opt-in cancellation context for tool handlers. A
tool spec may declare cancellation support; for those tools the executor
passes a thread-safe cancellation token as a second handler argument and
sets it when the timeout expires. Legacy one-argument handlers keep their
current behaviour. The returned result remains `timeout`; this chunk does
not pretend that an uncooperative Python thread can be forcibly killed.

**Files:** `src/percival_core/registry.py`;
`src/percival_core/executor.py`; `src/percival_core/__init__.py`;
`tests/test_foundation.py`.

**Acceptance:** A cancellation-aware synthetic handler that would wait
for two seconds exits promptly after a 0.1-second timeout sets its token;
the executor returns `timeout` in under 0.5 seconds and audits
`task.timeout`. Existing legacy timeout and deterministic executor tests
still pass. Run the targeted foundation tests, then the full suite.

**Depends on:** None.

### P-05 — Account for abandoned legacy invocations

**Objective:** For non-cancellation-aware handlers, observe the abandoned
future's eventual completion and append a separate audit event:
`task.abandoned_completed` or `task.abandoned_failed`. Record task and
tool identifiers only, never abandoned output. The original `timeout`
result is immutable and must not be rewritten as a success or failure.

**Files:** `src/percival_core/executor.py`; `tests/test_foundation.py`.

**Acceptance:** Use event-controlled synthetic handlers rather than a
race-prone sleep. After a timeout, release one handler to complete and
assert exactly one `task.abandoned_completed` audit event and no
`task.completed` event for that task; repeat with a failing handler and
assert `task.abandoned_failed`. Run the targeted foundation tests, then
the full suite.

**Depends on:** P-04.

### P-06 — Adversarial redaction hardening

**Objective:** Harden `percival_core.audit.redact` against common key and
secret-shape variants without turning ordinary prose into redacted mush.
Normalise sensitive key matching across case, hyphens, and underscores;
cover names such as `client_secret`, `access-token`, `auth_token`, and
`private-key`; add a bounded set of synthetic token shapes used by the
test corpus.

**Files:** `src/percival_core/audit.py`; `tests/test_audit.py` (new).

**Acceptance:** A table-driven synthetic corpus places sentinel secrets
in nested dictionaries, lists, tuples, free text, and values under variant
key names. After `AuditLog.record()` and read-back, no sentinel substring
appears in the stored JSON. Benign fixtures such as “token of
appreciation”, “secretary”, and “passwordless” remain unchanged. Run
`python3 -m unittest discover -s tests -p 'test_audit.py'`, then the full
suite.

**Depends on:** None.

---

## Friend registry (F-001 remainder)

### P-07 — Persistent synthetic friend-record store

**Objective:** Add a local SQLite `FriendRegistry` for friend records:
stable `friend_id`, display name, home stop ID, pickup label, opaque
contact-route string, tier, active flag, and creation/update timestamps.
Validate the tier and require a non-empty stop ID containing a feed
prefix. Do not add a street-address or geocoding field.

**Files:** `src/percival_core/friend_registry.py` (new);
`src/percival_core/__init__.py`; `tests/test_friend_registry.py` (new).

**Acceptance:** Using synthetic records in a temporary database, create,
read, update, deactivate, close, reopen, and list records. Duplicate IDs
and invalid tiers or stop IDs raise `ValueError`; deactivated records are
excluded from the default list. Run
`python3 -m unittest discover -s tests -p 'test_friend_registry.py'`, then
the full suite.

**Depends on:** None.

### P-08 — Persisted inner-tier eligibility

**Objective:** Add the registry's eligibility boundary. Only active,
inner-tier records can be converted to `FriendRef`; other records raise
`NotInnerTierError`. Tier changes require an explicit actor string, take
effect immediately, persist across reopen, and are written to an attached
`AuditLog` when one is supplied.

**Files:** `src/percival_core/friend_registry.py`;
`tests/test_friend_registry.py`.

**Acceptance:** An inner-tier synthetic record converts successfully;
changing it to another tier makes conversion fail immediately and after
reopen; changing it back with an explicit actor restores eligibility.
Assert the audit sequence contains both tier changes. Run the targeted
friend-registry tests, then the full suite.

**Depends on:** P-07.

### P-09 — Friend-registry to `bring_to_me` integration

**Objective:** Add an adapter that loads an eligible stored record,
constructs the existing `FriendRef` without exposing the contact route,
and calls `assess_visit()` with an injected `AtlasClient`. Missing
records raise a named lookup error; inactive or non-inner records fail
before any Atlas transport call.

**Files:** `src/percival_core/friend_registry.py`;
`src/percival_core/__init__.py`; `tests/test_friend_registry.py`.

**Acceptance:** Reuse the stubbed Atlas transport pattern from
`tests/test_bring_to_me.py`. An inner synthetic record produces both
assessment modes; missing, inactive, and non-inner records produce zero
transport calls. Assert the resulting plan object's friend block contains
no contact-route value. Run the targeted friend-registry and
bring-to-me tests, then the full suite.

**Depends on:** P-08.

---

## Workflow engine and mission ledger

### P-10 — Persist immutable plan-object snapshots

**Objective:** Add a SQLite `MissionLedger` that stores a versioned
F-001 plan object as a canonical JSON snapshot. A mission records its ID,
explicit friend ID, selected mode, service date, creation time, initial
`planned` status, and a SHA-256 hash of the canonical snapshot. Snapshots
are immutable through the public API and are verified against the hash on
read.

**Files:** `src/percival_core/missions.py` (new);
`src/percival_core/__init__.py`; `tests/test_missions.py` (new).

**Acceptance:** Save a synthetic plan, close and reopen the ledger, and
assert deep equality on read-back. Duplicate mission IDs conflict;
unsupported plan versions are rejected; direct database tampering with
the snapshot causes a named integrity error on read. Run
`python3 -m unittest discover -s tests -p 'test_missions.py'`, then the
full suite.

**Depends on:** P-09.

### P-11 — Mission lifecycle state machine

**Objective:** Add persisted lifecycle transitions and transition history
to `MissionLedger`. The allowed initial graph is:
`planned → draft_attached`, `planned → cancelled`,
`draft_attached → awaiting_approval`, `draft_attached → cancelled`,
`awaiting_approval → approved`, `awaiting_approval → rejected`, and
`awaiting_approval → cancelled`. Every other transition is refused.
Later chunks may extend the graph only through their own cards.

**Files:** `src/percival_core/missions.py`; `tests/test_missions.py`.

**Acceptance:** Table-test every allowed transition and representative
forbidden transitions, including `planned → sent` and
`rejected → approved`. Assert state and ordered transition history survive
close/reopen and that rejected and cancelled are terminal in this graph.
Run the targeted mission tests, then the full suite.

**Depends on:** P-10.

### P-12 — Draft-outbox storage

**Objective:** Add a SQLite `DraftOutbox` for objects returned by
`draft_outreach()`. Store mission ID, draft ID, mode, recipient friend ID,
text, SHA-256 content hash, creation time, and status
(`current`, `superseded`, or `discarded`). A new current draft supersedes
the previous current draft for the same mission. Reject any object whose
`requires_owner_approval` value is not true. This module contains no
transport or send method.

**Files:** `src/percival_core/outbox.py` (new);
`src/percival_core/missions.py`; `src/percival_core/__init__.py`;
`tests/test_outbox.py` (new).

**Acceptance:** Store and reopen a synthetic draft; add a second draft
and assert the first is superseded; assert a changed text produces a
different hash; reject a draft for another mission/mode and an unlabelled
draft. Assert the module's public surface contains no send/transmit
operation. Run
`python3 -m unittest discover -s tests -p 'test_outbox.py'`, then the full
suite.

**Depends on:** P-11.

### P-13 — Owner-approval records bound to a draft hash

**Objective:** Add persistent approval records for one exact action:
sending one exact draft. An approval binds owner actor, mission ID, draft
ID, content hash, scope `send_draft`, issue time, optional expiry, and
revoked/consumed state. `verify()` succeeds only for an exact, current
match. This chunk implements records and verification only, not dispatch.

**Files:** `src/percival_core/approvals.py` (new);
`src/percival_core/outbox.py`; `src/percival_core/__init__.py`;
`tests/test_approvals.py` (new).

**Acceptance:** An exact synthetic approval verifies after close/reopen.
Approvals fail verification when the mission, draft, hash, or scope
differs, and when expired or revoked. Assert verification alone does not
consume the approval. Run
`python3 -m unittest discover -s tests -p 'test_approvals.py'`, then the
full suite.

**Depends on:** P-12.

### P-14 — Approval-gated dispatch with a fake sender

**Objective:** Add a `GatedDispatcher` that accepts an injected sender
callable but implements no real transport. Dispatch loads the mission,
its current draft, and an approval; it calls the sender exactly once only
after exact verification, then marks the approval consumed and the
mission `sent`. Any failed check leaves the sender uncalled and records
an audited refusal.

**Files:** `src/percival_core/dispatch.py` (new);
`src/percival_core/approvals.py`; `src/percival_core/missions.py`;
`src/percival_core/outbox.py`; `src/percival_core/__init__.py`;
`tests/test_dispatch.py` (new).

**Acceptance:** With a counting fake sender, no approval, expired
approval, revoked approval, superseded draft, and hash mismatch each
produce zero sender calls. One exact approval produces one call; a second
dispatch attempt is refused and the count remains one. Run
`python3 -m unittest discover -s tests -p 'test_dispatch.py'`, then the
full suite.

**Depends on:** P-13.

### P-15 — Thin visit-workflow assembly

**Objective:** Add a `VisitWorkflow` coordinator over the existing
pieces. It creates a mission from a plan object, generates and stores a
draft for a feasible mode, advances the mission to `awaiting_approval`,
and returns a status snapshot. Dispatch is delegated only to P-14's
gated dispatcher; the workflow adds no transport of its own.

**Files:** `src/percival_core/workflow.py` (new);
`src/percival_core/missions.py`; `src/percival_core/outbox.py`;
`src/percival_core/__init__.py`; `tests/test_workflow.py` (new).

**Acceptance:** Using synthetic plan and draft fixtures, a feasible mode
creates one mission and one current draft in `awaiting_approval`; a
non-feasible mode cannot create a draft. Approval plus the fake sender
from P-14 completes the sequence once. Assert no contact-route value is
copied into the mission snapshot or outbox record. Run
`python3 -m unittest discover -s tests -p 'test_workflow.py'`, then the
full suite.

**Depends on:** P-09 and P-14.

---

## F-002 and F-003 plan-object generation

### P-16 — Bonfire plan object from supplied evidence

**Objective:** Add a pure builder for a versioned bonfire plan object.
Inputs are a place reference, date, synthetic guest IDs with already
computed feasibility verdicts and last-return times, and conditions
evidence supplied as `{value, source, status}` records for weather, fire
status, and sunset. The builder produces a deterministic supplies
checklist, timeline, evidence section, unresolved-items section, and a
draft invitation labelled as requiring owner approval. It must not fetch
weather, fire, place, or transport data.

**Files:** `src/percival_core/bonfire.py` (new);
`src/percival_core/__init__.py`; `tests/test_bonfire.py` (new).

**Acceptance:** A golden synthetic fixture with two feasible guests
produces the expected checklist quantities, timeline order, and draft.
Changing one guest to `unknown` changes the plan status to
`needs_attention`, names the missing evidence, and removes any “all set”
summary. Missing conditions remain `unknown`, never invented. Run
`python3 -m unittest discover -s tests -p 'test_bonfire.py'`, then the
full suite.

**Depends on:** P-07.

### P-17 — Errand-day validation and conflict detection

**Objective:** Add the data model and validator for an errand day. Each
stop has an ID, location reference, opening and closing times, expected
duration, optional hard appointment, and items to bring. Travel durations
are supplied as an explicit matrix. For a proposed sequence, detect
arrival after closing, insufficient time before a hard appointment, and
missing travel data. Missing travel data is `unknown`, never zero.

**Files:** `src/percival_core/errands.py` (new);
`tests/test_errands.py` (new).

**Acceptance:** Synthetic fixtures produce exact conflict codes for a
late closing time, a hard-appointment collision, and a missing travel
leg; a valid proposed sequence produces no conflicts. Run
`python3 -m unittest discover -s tests -p 'test_errands.py'`, then the
full suite.

**Depends on:** None.

### P-18 — Errand itinerary and merged checklist

**Objective:** Extend P-17 with a deterministic itinerary builder.
Hard appointments remain fixed chronological anchors. Other stops are
considered by earliest closing time and inserted only where the supplied
travel matrix proves the sequence fits. A stop that cannot be placed is
returned as `unplaced` with its reason, not silently dropped or moved
past a hard commitment. Emit timed stops and one merged bring-list that
preserves which stop needs each item.

**Files:** `src/percival_core/errands.py`;
`src/percival_core/__init__.py`; `tests/test_errands.py`.

**Acceptance:** A golden synthetic day produces the exact expected order,
departure/arrival/service times, and merged checklist. An impossible stop
appears in `unplaced` with the P-17 conflict code; no scheduled stop ends
after its closing time. Run the targeted errands tests, then the full
suite.

**Depends on:** P-17.

---

## F-004 verdict-model extension

### P-19 — Rideshare quote contract, with no verdict change

**Objective:** Define a stub-friendly rideshare quote contract for
`bring_to_me`: a provider callable and a validated quote record covering
one named gap (`return` or `round_trip`), provider label, amount in minor
currency units, currency, pickup and drop-off stop IDs, and expiry.
Extend each mode result with `transit_verdict` and
`rideshare_quote: None`. Do not change any verdict in this chunk and do
not add network code or credentials.

**Files:** `src/percival_core/bring_to_me.py`;
`src/percival_core/__init__.py`; `tests/test_bring_to_me.py`.

**Acceptance:** Existing assessment tests retain their original verdicts
while exposing the new fields. A synthetic quote serialises into the plan
object exactly; negative amounts, unsupported currencies in the fixture
set, and expired quote objects fail validation. Run the targeted
bring-to-me tests, then the full suite.

**Depends on:** None.

### P-20 — `feasible_via_rideshare` fallback rules

**Objective:** Add the first-class verdict `feasible_via_rideshare` to
`assess_visit()` through an optional quote provider. Call the provider
only when the transit verdict is `not_feasible`. A complete, unexpired
quote for the missing gap may upgrade the combined verdict while
preserving `transit_verdict: not_feasible`, the transit reason, quote
cost, and provider label as evidence. Never call the provider for a
transit `feasible` or `unknown` mode, and never blend the quote into a
plain `feasible` verdict. `draft_outreach()` continues to refuse this
verdict until owner-facing copy is separately approved.

**Files:** `src/percival_core/bring_to_me.py`;
`tests/test_bring_to_me.py`.

**Acceptance:** Stub-provider matrix: transit feasible → provider not
called; transit unknown → provider not called; missing return plus a
complete return quote → `feasible_via_rideshare`; provider no-service →
`not_feasible`; provider unavailable or incomplete quote → combined
verdict `unknown` with `transit_verdict: not_feasible` preserved; expired
quote → no upgrade. Assert `draft_outreach()` raises for
`feasible_via_rideshare`. Run the targeted bring-to-me tests, then the
full suite.

**Depends on:** P-19.

---

## UI-surface preparation

### P-21 — Friend-card button view model for plan states

**Objective:** Add a pure, data-only view-model function for one friend
card and mode. It maps a plan object to `state`, `headline_key`,
`detail_key`, `reason`, `enabled_action`, and an accessibility label.
States are `feasible`, `not_feasible`, `unknown`, and
`feasible_via_rideshare`. `unknown` maps to an investigate/details
action and never to language meaning “impossible”. This chunk contains
no visual design, markup, styling, or UI-framework import.

**Files:** `src/percival_core/button_view_model.py` (new);
`src/percival_core/__init__.py`;
`tests/test_button_view_model.py` (new).

**Acceptance:** Table-test every verdict and a missing-mode plan object
for exact view-model dictionaries. Only transit `feasible` enables
`draft_outreach`; `feasible_via_rideshare` enables `view_quote`; unknown
enables `investigate`; not feasible enables no primary action. Run
`python3 -m unittest discover -s tests -p 'test_button_view_model.py'`,
then the full suite.

**Depends on:** P-20.

### P-22 — Button view model for workflow and approval states

**Objective:** Extend P-21 with mission, outbox, and approval status.
The view model distinguishes: no mission, draft awaiting approval,
approved for the current draft hash, approval stale after the draft was
superseded, sent, rejected, and cancelled. An `unknown` plan verdict
overrides workflow presentation and remains an investigate state. The
module returns data flags only and gains no send operation.

**Files:** `src/percival_core/button_view_model.py`;
`tests/test_button_view_model.py`.

**Acceptance:** Table-test the full state matrix. `send_enabled` is true
only for an approved mission whose approval hash matches the current
draft; a superseded draft maps to locked with reason
`approval_stale`; sent maps to completed; rejected and cancelled map to
restart-required. Assert the module's public surface has no send or
dispatch function. Run the targeted view-model tests, then the full
suite.

**Depends on:** P-15 and P-21.

---

## Independent adapter

### P-23 — Local-model adapter over an injected transport

**Objective:** Add a factory that creates a `ToolSpec` for a host-
configured local model. The host must supply the endpoint label, model
name, and a transport callable; the adapter creates no grant and performs
no discovery. It translates the transport's Ollama-shaped JSON response
into text and converts transport errors, timeouts, and malformed replies
into `ToolUnavailable`, allowing the executor's existing degradation path
to work. Tests use a fake transport and make no network calls.

**Files:** `src/percival_core/local_model.py` (new);
`src/percival_core/__init__.py`; `tests/test_local_model.py` (new).

**Acceptance:** Fake-transport success returns the response text through
the executor; connection error, timeout, HTTP failure, and malformed JSON
each produce a `degraded` executor result rather than an unhandled
exception. Assert the factory itself registers no agent, tool, or grant.
Run
`python3 -m unittest discover -s tests -p 'test_local_model.py'`, then the
full suite.

**Depends on:** P-06.

---

## RESERVED — owner/Astra-class, not chunks

### P-001 privacy architecture and key/recovery design

P-001's end-to-end encryption design is **reserved** for the owner and an
Astra-class security session. It is not Luna work and no chunk above
implements, prepares, or substitutes for it.

Reserved questions include the threat model; key generation, storage,
device binding, backup, recovery, and loss; identity verification;
metadata exposure; encrypted storage for friend records, missions, and
audit data; and the honest recovery limits the owner accepted in
principle. Security-boundary changes require Branden's explicit approval
under `AGENTS.md`.

Until that design is approved, the SQLite chunks in this file are local
persistence only. They must not be described as end-to-end encrypted or
as protecting intimate data against a compromised device or account.

## NOT CHUNKED — and why

- **Production service boundary and live tool exposure.** The FastAPI
  versus standard-library decision, authentication/session model, and
  boundary authorisation remain open. This is a security-boundary change
  requiring owner approval; the existing Vercel surface stays inert and
  dry-run-only.
- **Hard process isolation for uncooperative handlers.** P-04 and P-05
  make timeout behaviour honest for cooperative and legacy handlers.
  Replacing threads with a process sandbox changes the execution and
  security architecture and is not a Luna-sized patch.
- **Real people's data.** No chunk imports, migrates, or seeds real
  names, contact routes, addresses, schedules, or mission history. That
  waits for the reserved P-001 design and separate owner direction.
- **Real messaging, booking, rideshare, or agency integrations.**
  Credentials, OAuth, provider terms, account state, and spending are
  outside these chunks. Only fake senders and stub quote providers are
  specified.
- **Live F-002 conditions providers.** Weather, fire-danger, burn-ban,
  and sunset sources require local authority/provenance choices and
  alert-threshold judgment. P-16 accepts supplied evidence; it does not
  choose or call a provider.
- **Live F-003 hours, place, and routing providers.** P-17 and P-18 use
  supplied hours and travel durations. Selecting live sources and
  resolving conflicting provenance is separate work.
- **Metro visual design and the actual button implementation.** The
  surface lives in the ZeroCloud/Metro work and requires design
  judgment. P-21 and P-22 provide only the tested data model it can bind
  to.
- **OpenClaw workspace skill.** A valid chunk would require a pinned
  OpenClaw version and installation verification on the target runtime;
  documentation alone cannot honestly satisfy its acceptance test.
- **Full M1 butler dispatch taxonomy.** Mission types, delegation
  policy, escalation rules, and cross-department priorities are not yet
  specified. The workflow chunks build the substrate without inventing
  that policy.

---

## F-005 mood-night substrate ("White girl wasted night" button)

Added 2026-11-14. These chunks decompose the honestly-chunkable
substrate of `FEATURE_QUEUE_muse.md` F-005: the mood-template data
model, cart assembly against a **fake** delivery provider, the
assembled-order presentation object, and its wiring into the existing
approval-gate machinery (P-13/P-14). The spend step reuses that
machinery — an order is dispatched only against an owner-approval
record bound to the order's exact content hash, exactly as a draft
send is. **No chunk here integrates a real delivery provider, holds a
credential, or places a real order**; real provider integration stays
under the NOT CHUNKED discipline above ("Real messaging, booking,
rideshare, or agency integrations").

**Consumption order addition:** P-24 → P-25; P-26 after P-24; P-27
after P-26, P-13, and P-14; P-28 after P-22 and P-27.

### P-24 — Mood-template data model

**Objective:** Add the pure data model for a mood template: a named
night (stable template ID and display name) resolving to a standing
basket — line items with label, quantity, and serves count (the
template's "for two" is data, not a comment), a preferred-store
label, and a per-item substitution policy whose default is
`never_upgrade`. Frozen dataclasses with validation and exact JSON
round-trip, following the existing record patterns. No storage, no
provider, no ordering.

**Files:** `src/percival_core/mood_templates.py` (new);
`tests/test_mood_templates.py` (new).

**Acceptance:** A synthetic fixture template named for the F-005
night (boxed rosé plus a charcuterie board, serves 2) round-trips
through JSON exactly, including the `never_upgrade` policy on the
wine item. Zero/negative quantity or serves, an empty basket, and an
off-vocabulary substitution policy each raise `ValueError`. Run
`python3 -m unittest discover -s tests -p 'test_mood_templates.py'`,
then the full suite.

**Depends on:** None.

### P-25 — Persistent mood-template store

**Objective:** Add a local SQLite store for mood templates following
the `FriendRegistry`/`MissionLedger` patterns: create, read, update,
deactivate, list (active only by default), persisted across
close/reopen. Templates are standing preferences owned by the
principal; the store records no orders, prices, or provider data.

**Files:** `src/percival_core/mood_templates.py`;
`tests/test_mood_templates.py`.

**Acceptance:** In a temporary database, create two synthetic
templates, update one's quantity, deactivate the other, close and
reopen, and assert exact read-back and that the deactivated template
is excluded from the default list. Duplicate template IDs are
rejected. Run the targeted mood-template tests, then the full suite.

**Depends on:** P-24.

### P-26 — Cart assembly against a fake delivery provider

**Objective:** Add a cart assembler that takes a mood template and an
injected provider callable. The provider returns per-item evidence:
available (with price in minor currency units) or unavailable. The
assembler produces a cart in exactly one of two states: `assembled`
(every item available as specified) or `needs_attention`. When an
item is unavailable, the cart records the gap **as evidence** — the
item, its unavailability, and any substitute the provider offered —
and Percival never silently swaps it in. For an item whose policy is
`never_upgrade`, an offered substitute labelled as an upgrade is
recorded as evidence and explicitly **not** accepted; the cart is
`needs_attention` with the item unresolved. This chunk contains no
network code, no credentials, and no order placement.

**Files:** `src/percival_core/mood_cart.py` (new);
`src/percival_core/__init__.py`; `tests/test_mood_cart.py` (new).

**Acceptance:** With stub providers: all-available → `assembled`
cart with exact items, quantities, and summed total; one item
unavailable with a same-tier substitute offered → `needs_attention`,
substitute present as evidence only, original item still listed as
unresolved; the `never_upgrade` wine item unavailable with an
upgrade substitute offered → `needs_attention`, substitute recorded
as rejected-upgrade evidence, never in the cart's accepted items.
Assert the module's public surface contains no order/send operation.
Run `python3 -m unittest discover -s tests -p 'test_mood_cart.py'`,
then the full suite.

**Depends on:** P-24.

### P-27 — Assembled-order presentation object and approval-gated dispatch

**Objective:** Build the owner-facing order object from a P-26 cart:
items and quantities, total in minor units with currency, and the
arrival estimate **as supplied evidence** (value plus provider
label, never presented as a promise), with substitution/unresolved
flags carried through. Persist the order with a SHA-256 content hash
(MissionLedger pattern). Dispatch goes only through the existing
approval machinery: an approval record (P-13) bound to this order's
exact hash under a distinct `place_order` scope, consumed by a
gated dispatcher (P-14 pattern) whose sender is an injected **fake**
order-sender. A `needs_attention` cart cannot become an order at
all. If the approvals module hard-codes its scope rather than
storing it as a field, stop and report per the stop-and-report rule
instead of widening it silently.

**Files:** `src/percival_core/mood_orders.py` (new);
`src/percival_core/approvals.py`; `src/percival_core/__init__.py`;
`tests/test_mood_orders.py` (new).

**Acceptance:** With a counting fake sender: no approval, expired
approval, approval for a different hash, and approval under the
`send_draft` scope each produce zero sender calls; one exact
`place_order` approval produces exactly one call and a second
dispatch attempt is refused. A `needs_attention` cart raises before
any order record exists. The presentation object for a fixture cart
shows the ETA labelled with its provider source. Run
`python3 -m unittest discover -s tests -p 'test_mood_orders.py'`,
then the full suite.

**Depends on:** P-13, P-14, and P-26.

### P-28 — Mood-button view model

**Objective:** Extend the button view model with the mood-night
card: a pure data mapping from template + cart + order state to
`state`, `headline_key`, `detail_key`, and `enabled_action`. States:
`ready` (cart assembled clean, action: review order),
`needs_attention` (substitution or unresolved evidence, action:
review evidence — never rendered as a failure or as "impossible"),
`awaiting_approval`, `approved`, `ordered` (fake-dispatched), and
`unknown` (no provider evidence yet, action: investigate). The
module returns data only and gains no order or send operation.

**Files:** `src/percival_core/button_view_model.py`;
`tests/test_button_view_model.py`.

**Acceptance:** Table-test every state for the exact view-model
dictionary. `place_order_enabled` is true only in `approved` with a
hash-matching approval (reusing P-27's states); `needs_attention`
enables only the evidence-review action; `unknown` enables only
investigate. Assert the module's public surface has no order,
dispatch, or send function. Run the targeted view-model tests, then
the full suite.

**Depends on:** P-22 and P-27.

### Not chunked (F-005)

- **Real delivery-provider integration (DoorDash or any other).**
  Accounts, OAuth/API credentials, provider terms, real pricing and
  availability, payment, and real order placement are outside these
  chunks — the same exclusion as every other real integration in
  this file. P-26/P-27 specify only stub providers and a fake
  sender.
- **The mood-button pattern as a general class.** F-005 notes the
  pattern generalises beyond one night. P-24 models one template
  shape honestly; abstracting a general mood/workflow class before
  a second mood exists is speculative architecture, not a chunk.
- **Companion staging (F-001 check, lights, music).** The queue
  lists these as proposals, each with its own approval. Bundling
  them into the mood workflow is a product decision for the owner,
  not substrate.
