# Percival — Feature Queue (Branden's rapid-fire requests)

_How this works (Branden, 2026-11-14): he dictates feature wants in no particular order; Ember queues them here, decomposes each into bounded slices, implements the small verifiable ones under the engineering handoff's merge auth, and scopes the big subsystems for Codex in CODEX_HANDOFF.md. Nothing here is implemented until it says so._

_Self-indulgent by design (Branden, 2026-11-14): "I'm building a self-indulgent piece of software." Percival is built for his household and his values first — not for a market — so its trade-offs resolve toward the principle rather than toward growth, retention, or recovery-rate metrics. That is why rulings like P-001's privacy-over-recovery come out the way they do._

_Product vision (Branden, 2026-11-14): Percival is a complete butler inside an app — transportation is only one of his departments; the full brief is the whole household (scheduling, communications, household operations, research, errands, delegated workflows), matching the percival repo's own charter. The buttons in this queue are the butler's services — each one a domestic act the butler quietly handles end-to-end (the backend included) so the people involved don't carry the friction. The Metro-style app surface (ZeroCloud playground) is where the butler lives; the Atlas and the workflow specs are his competence behind the door._

_Design source (Branden, 2026-11-14): these buttons are reverse-engineered from the small acts of domestic work that made his relationship with Cass work — the everyday care logistics that actually held a shared life together. He names the act; the workflow gets built backwards from it. Treat each request as a field report from a real household, not an abstract feature idea: the act worked once, in real life, and the software's job is to make it repeatable._

## F-001 — "Bring to me" button (supported friends)
- **Requested:** 2026-11-14, by Branden in chat.
- **What he said, in substance:** In Percival, a "bring to me" button for supported friends: it creates workflows to bring friends to him, or bring him to friends, and "deals with the backend."
- **Decomposition (Ember):**
  1. **Friend record** — a supported friend = a person with a known home base / pickup point and contact route. (Registry design now builds on the adopted `percival_core` registry — PR #6 foundation seed, adopted 2026-11-14, ADR-006; the production friend-record registry remains Codex-class work on that base.)
  2. **Two modes:** *Bring them to me* (friend's location → Branden, with their feasible return) and *Bring me to them* (Branden → friend, with his feasible return). Both are round-trip feasibility questions — the Transit Atlas Mobility Bubble machinery (`/api/v1/reachability` + return-feasible planning) answers them directly.
  3. **Workflow generation** — a plan object: proposed journey(s) both directions, timing that leaves meaningful time together, and draft outreach (message to the friend) — **draft only**. Percival's standing rule: no model or workflow independently authorizes real-world actions; messaging the friend, booking, or spending requires Branden's explicit approval at send time.
  4. **Button surface** — one tap in the Percival UI on a friend's card; states: feasible / not feasible on verified data / unknown (missing data is not "impossible").
- **The point of it (Branden, 2026-11-14):** little frictions. He wants to hang out with a friend without the friend having to worry about how to get to him or how to get home. The system absorbs the logistics worry so the guest never carries it — what the friend receives is a settled plan ("here's how you'll get here, here's how you'll get home"), not a problem to solve. This is the design test for the whole button: if the friend still has to think about transport, the workflow failed.
- **Sizing:** Workflow engine + friend registry = Codex-class (big). The feasibility core already exists in the Atlas work (Priority A). Ember-sized slices: this spec; the feasibility-query contract between Percival and the Atlas API.
- **Elaboration (Branden, 2026-11-14, dictated):** the primary case is a **close friend or partner** — someone in the inner tier, enabled in advance — and the headline mode is **"come to me"**: one function that brings that person to him, the system dealing with the whole backend (their journey here AND their way home). The relationship tier is part of the design: this is not a button for acquaintances; it exists for the people close enough that "come to me" needs no explanation attached.
- **Status:** FEASIBILITY CORE BUILT (2026-11-14) — `src/percival_core/bring_to_me.py`: inner-tier-gated `assess_visit` (both modes, three-state verdicts, return feasibility composed from the Atlas `plan` endpoint's `return=1&visit=` support) + `draft_outreach` (draft-labelled, no send path anywhere in the module). 15 new tests (14 stubbed-transport unit + 1 live Atlas integration, run and passing against the real six-feed data); full suite 39/39. Merged into `main` via the `f001-feasibility-slice_muse` PR. REMAINING (Codex-class): persistent friend registry on the adopted `percival_core` registry, workflow engine, and the UI button surface. (Foundation blocker cleared 2026-11-14: PR #6 adopted as the foundation seed by owner decision, recorded as ADR-006, and merged into `main` — merge commit c2bb829, post-merge suite re-verified 24/24.)

## F-002 — "Plan a bonfire" button
- **Requested:** 2026-11-14, by Branden in chat (second rapid-fire request).
- **What he said, in substance:** A button in Percival that plans a bonfire.
- **Decomposition (Ember):**
  1. **Inputs:** place (a known bonfire-capable spot — his places or a friend's), date/evening, guest list (supported friends, per F-001's records).
  2. **Feasibility layer:** can everyone actually get there and home again that night — last-trip/return checks via the Transit Atlas; late-evening service gaps surface as "unknown/needs a ride plan," never silently fine.
  3. **Conditions layer:** weather forecast for the evening, fire-danger/burn-ban status for the town, daylight/sunset time — presented as evidence, and a bad-conditions result says so plainly.
  4. **Plan object:** supplies checklist (wood, seating, food/drink, lighting, music), timeline (arrive, light, last buses, wind-down), and draft invitations — **draft only**; sending anything needs Branden's explicit approval, per Percival's contract.
- **Sizing:** Plan-object + checklist generation = Ember-sized once F-001's friend/place records exist. Conditions/feasibility integrations = bounded slices. No subsystem build.
- **Status:** QUEUED — spec only, nothing built.

## F-003 — "Plan a day off / errands" button
- **Requested:** 2026-11-14, by Branden in chat (third rapid-fire request).
- **What he said, in substance:** A button that plans a day off — errands run as one planned day.
- **Decomposition (Ember):**
  1. **Inputs:** the errand list (dictated in any order — shops, pharmacy, post office, returns, the MPB drop-off class of errand), the day, his start time, hard appointments if any.
  2. **Sequencing layer:** order the stops into one sane route — opening hours as constraints, geography/transit via the Atlas (or scooter legs), no stop scheduled after its closing time; conflicts surface as evidence, not silent reshuffles.
  3. **Plan object:** a timed itinerary — leave home, each stop with its window and what to bring (receipts, parcels, ID), buffers, the trip home; plus a single checklist merged across stops.
  4. **Reality rules:** anything the data can't verify (a shop's hours unconfirmed, a route unknown) is labelled unknown; the plan never invents an open hour or a bus that doesn't exist.
- **Sizing:** Itinerary/checklist generation = Ember-sized on top of Atlas routing. Errand-list capture from dictation/email = bounded slice.
- **Status:** QUEUED — spec only, nothing built.

## F-004 — Multi-modal completion layer (rideshare gap-filling)
- **Requested:** 2026-11-14, by Branden in chat (vision elaboration on F-001).
- **What he said, in substance:** Percival grows APIs for Uber, Lyft, and the major transit agencies; Percival itself makes routing and mapping available "so two people can just make it work."
- **Decomposition (Ember):**
  1. **Transit first, rideshare as the gap-filler.** The Atlas bubble already classifies the world into feasible / not feasible / unknown on transit alone. The completion layer answers the *not feasible* cases: when transit has no feasible return, a rideshare leg (to a railhead, or the whole last leg) can convert the verdict — shown honestly as feasible-via-rideshare, with the cost visible, never silently blended into a "transit" answer.
  2. **Agency APIs beyond GTFS** — real-time positions/alerts where agencies publish them, upgrading published-schedule answers toward live ones, with provenance labelled per answer.
  3. **Percival as the router of routers** — one feasibility question in, every mode considered underneath, one settled plan out. The two people see none of the machinery.
- **Sizing:** Codex-class integrations (third-party API keys, OAuth, spend paths — booking/spending stays behind Branden's explicit approval per Percival's contract, permanently). Ember-sized: this spec; the verdict-model extension (feasible-via-rideshare as a first-class state) in the F-001 slice's plan object.
- **Status:** QUEUED — vision/spec only, nothing built.

## P-001 — Privacy as a first principle (owner directive, 2026-11-14)
- **Branden's words, in substance:** the app is built from the ground up with end-to-end encryption — "military grade within reason" — because using it confers a lot of trust in both directions (the user trusts the app; the people in it trust each other through it).
- **Why it is load-bearing here (Ember):** a "come to me" system holds the most sensitive dataset a consumer app can hold — where people live, when they are home, when they are travelling, and who matters to whom. The inner-tier list alone is a map of a person's intimate life. A breach or a curious server operator would expose exactly the people the system exists to protect.
- **Design commitments that follow:**
  1. **End-to-end encryption for the substance** — plans, locations, messages, friend records: readable only on the participants' devices; any server Percival uses relays ciphertext it cannot read.
  2. **Metadata minimisation** — collect the least the workflow allows; what is not stored cannot leak, be subpoenaed into usefulness, or be repurposed.
  3. **Local-first where possible** — the Atlas pattern (loopback, own machine) is the instinct to keep: the closer computation stays to the person's own devices, the smaller the trust surface.
  4. **Honest tension, named now:** E2E plus a butler who acts on your behalf means keys live on devices and account recovery is genuinely hard (lose the keys, lose the history — by design). "Within reason" is the owner's own bound: consumer-grade usability is a requirement, not a betrayal of the principle. Key/recovery design is Codex-class security work and requires Branden's explicit approval per Percival's contract (security-boundary changes are never routine merges).
- **Owner ruling on the tension (Branden, 2026-11-14):** "That's a trade-off that I would pay personally." The hard-recovery / lose-the-keys-lose-the-history cost is ACCEPTED at the principle level — privacy wins the tie. (Product consequence to design for, not relitigate: key backup/recovery UX must be honest about what it can and cannot restore.)
- **Status:** PRINCIPLE — governs F-001 through F-004 and everything after; nothing here is implemented yet.
