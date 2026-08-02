# AGENT.md — Instructions for AI Coding Agents

This file is for any AI coding agent (Claude Code, or similar) working in this repository. Read this
in full, plus [`RULES.md`](./RULES.md), before writing or modifying any code. If anything here
conflicts with a live instruction from the project owner in the current session, the live instruction
wins — but flag the conflict rather than silently resolving it.

---

## 1. What this project is (one paragraph)

OptiMart is a hyper-local food-waste rescue platform: a FastAPI backend scores grocery inventory
batches against expiry timelines using a Scikit-Learn model informed by weather and demand data, picks
an optimal markdown, and — when a threshold is crossed — triggers geofenced SMS/WhatsApp flash-sale
alerts via Twilio to nearby consumers and NGOs. Claimants reserve (Redis TTL lock), pay (Stripe/
Razorpay), and choose pickup or delivery. A React frontend serves the public claim page, the store
dashboard, and the NGO standing-order portal. Full context: `README.md` and the project playbook PDF.

## 2. Before doing anything

1. Read `RULES.md` — it governs branching, commits, permission gates, and documentation. It is not
   optional context; it is binding process.
2. Read `STATUS.md` to find the current phase and what's already built. **Do not assume the repo is
   empty just because your context window doesn't show prior work** — check `STATUS.md` first.
3. Read `DECISIONS.md` to avoid re-litigating or silently reversing a decision that was already made
   and reasoned through.
4. Confirm which phase you're being asked to work on. If it's ambiguous, ask — don't guess and start
   coding across phase boundaries.

## 3. Operating constraints specific to this repo

- **Stay inside the current phase's scope.** See `RULES.md` Rule A. This is the single most important
  constraint — hackathon-style projects die from scope creep more than from any technical failure.
- **Ask before pushing, merging, starting a new phase, adding a dependency, or touching a completed
  phase's code.** See `RULES.md` Rule C. This applies even if you are highly confident the change is
  correct and low-risk.
- **Update `STATUS.md` and `DECISIONS.md` as you go**, not as a final step. If you finish a work
  session without having touched these files and you made any non-trivial decision, that's a signal
  you skipped a required step — go back and log it before considering the task done.
- **Never fabricate the appearance of real data.** The ML training data is synthetic by design (see
  `ARCHITECTURE.md` §6) — do not present model outputs as if they came from real retailer history.
  Label synthetic data clearly in code comments and docs.
- **Secrets never get committed.** If you need an API key to test something, use `.env` (gitignored)
  and reference it via `.env.example` with a placeholder — never hardcode a key, even temporarily,
  even in a comment.

## 4. Code conventions

| Layer | Convention |
|---|---|
| Python (backend) | PEP 8, type hints on public functions, `black` for formatting, `ruff` for linting. FastAPI route handlers stay thin — business logic lives in `app/core` or `app/tasks`, not inline in route functions. |
| SQL / migrations | Alembic for all schema changes — no manual `ALTER TABLE` outside a migration file. |
| React (frontend) | Functional components + hooks, Tailwind utility classes (no ad hoc CSS files unless a component genuinely needs it), Prettier for formatting. |
| Celery tasks | Idempotent by design — a task re-run (e.g. after a worker crash) must not double-charge, double-notify, or double-reserve. |
| Commits | Follow `RULES.md` Rule B format: `[phase-<n>] <type>: <description>`. |

## 5. Key files map

```
backend/app/api/inventory.py     — batch ingestion (CSV/manual/OCR)
backend/app/api/claims.py        — reservation, claim confirmation, fulfillment status
backend/app/api/payments.py      — Stripe/Razorpay checkout + webhook receivers
backend/app/api/standing_orders.py — NGO/shelter priority rules
backend/app/ml/pricing_model.py  — Model A: markdown/price optimization
backend/app/ml/segment_model.py  — Model B: B2C vs B2B/NGO routing classifier
backend/app/tasks/scan.py        — Celery beat: periodic expiry-risk scan
backend/app/tasks/dispatch.py    — Twilio SMS/WhatsApp dispatch + inbound webhook handling
frontend/src/pages/claim/        — public, no-login claim page
frontend/src/pages/dashboard/    — store admin dashboard
frontend/src/pages/ngo/          — standing-order portal
```
(This map reflects the intended structure from `ARCHITECTURE.md`; if the actual repo has diverged,
`STATUS.md` and the real file tree are the source of truth — update this map if it goes stale.)

## 6. When you're not sure

Default to asking a short, specific question rather than guessing on anything that touches: scope
boundaries, payment logic, data privacy handling, or anything `DECISIONS.md` suggests was deliberately
chosen a certain way for a reason not obvious from the code alone.

## 7. Definition of "done" for any task you're given

A task is done when: it works end-to-end for its stated scope, relevant tests pass or are added,
`STATUS.md` reflects the new state, any decision worth remembering is in `DECISIONS.md`, and you have
explicitly asked before pushing/merging per Rule C. Announcing you're "done" without these is not done.
