# RULES.md — OptiMart Working Rules

These rules are **binding** for every contributor to this repository — human or AI agent. They exist
because this project is being built under a short, phased timeline (see the Implementation Roadmap in
the project playbook) where scope creep and undocumented decisions are the two things most likely to
sink it. `AGENT.md` layers AI-agent-specific onboarding on top of this file; this file is the source
of truth for *how work happens* regardless of who's doing it.

---

## Rule A — Phase Discipline

- The project is broken into numbered **Phases** 0–7 (Setup → Inventory Core → Markdown Engine →
  Geofencing &amp; Claims → Comms → Payments &amp; Fulfillment → Dashboard &amp; Polish → Demo Rehearsal).
- Work happens on **one phase at a time**. Do not implement functionality that belongs to a later
  phase, even if it's convenient to "grab while you're in the file."
- If work necessary to finish the current phase turns out to require something out of scope (a
  missing dependency, an architectural gap, an ambiguous spec), **stop and log it** in `STATUS.md`
  under "Blockers / Scope Questions" instead of quietly expanding scope to route around it.
- A phase is complete only when: its stated deliverable works end-to-end, `STATUS.md` reflects it
  under "Built," any non-trivial decision made along the way is in `DECISIONS.md`, and the project
  owner has explicitly signed off.

## Rule B — Branching &amp; Commit Hygiene

- One branch per phase: `phase-<n>-<short-slug>` (e.g. `phase-2-markdown-engine`).
- **No direct commits to `main`.** `main` only receives approved, completed phase branches via PR/merge.
- Commit early and often within a phase branch — one commit per meaningful working increment, not one
  giant commit at the end.
- Commit message format: `[phase-<n>] <type>: <description>`
  Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`.
  Example: `[phase-3] feat: add Redis TTL reservation lock on claim creation`

## Rule C — Permission Gates

Explicit go-ahead is required, every time, before:

1. Pushing any commit to the remote.
2. Opening or merging a pull request.
3. Starting a new phase — even if the current one feels finished.
4. Installing a dependency not already agreed in the current phase's plan.
5. Modifying code belonging to a previously completed (merged) phase.

State *what* you want to do and *why* in one or two sentences when asking — keep it short.

## Rule D — Continuous Documentation

Three files are updated **as work happens**, not retroactively:

- **`STATUS.md`** — updated after every commit or phase boundary. Current phase, what's built, what's
  in progress, what's not started, and any blockers.
- **`DECISIONS.md`** — append-only log, one entry per non-trivial technical decision, written at the
  time the decision is made. Include the rationale and alternatives considered, not just the outcome.
- **Root `README.md` "Project Status" pointer** — always points at the current phase.

An out-of-date `STATUS.md` is treated as worse than a missing one — it actively misleads the next
contributor. Keeping it current is not optional busywork.

## Rule E — Testing &amp; Definition of Done

- Prioritize a small number of meaningful tests over broad low-value coverage: reservation locking
  (no double-claims under concurrent requests), price-optimization logic, claim state transitions
  (`reserved → paid → fulfilled` and the expiry/timeout path), and Twilio/payment webhook handling.
- Every PR into `main` must include or update tests for the logic it touches, or an explicit note in
  the PR description explaining why not (e.g. pure UI polish).

## Rule F — Security &amp; Data Handling (see `SECURITY.md` for detail)

- Never commit real secrets, API keys, or `.env` files — only `.env.example` with placeholder values.
- Raw payment card data never touches this codebase's own database — Stripe/Razorpay tokenization
  only.
- User geolocation is coarse and opt-in, not continuous tracking.

## Rule G — Priority Order Under Time Pressure

If the build window compresses, cut scope in this order (most to least expendable), per the
playbook's Chapter 8.2:

1. Descending-price live auction view (nice-to-have visual, not core).
2. WhatsApp integration → fall back to SMS-only.
3. Real courier/delivery routing → fall back to a static "volunteer queue" list.
4. Inbound "reply YES" SMS claiming → fall back to link-only claiming.
5. Never cut: the core loop of expiry detection → dynamic pricing → geofenced alert → claim → payment.
   That loop is the entire thesis of the project and must always be demoable.

## Rule H — Communication Cadence

- Start of each phase: a one-line restatement of scope and deliverable, confirmed before work begins.
- End of each phase: a short summary of what was built, what was deferred, and a pointer to any new
  `DECISIONS.md` entries — then wait for go-ahead before branching into the next phase.

---

*Companion files: [`AGENT.md`](./AGENT.md) for AI-agent-specific conventions,
[`CONTRIBUTING.md`](./CONTRIBUTING.md) for human contributor setup/PR process,
[`STATUS.md`](./STATUS.md) and [`DECISIONS.md`](./DECISIONS.md) as the living logs referenced above.*
