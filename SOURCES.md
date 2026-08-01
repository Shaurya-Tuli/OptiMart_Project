# Sources & citations

Every reused piece of code, design pattern, dashboard component, or
third-party integration approach is logged here **at the time it's
used** — not reconstructed from memory before submission. Anything
built fresh during the hackathon window gets no entry; this file only
tracks what is *not* original to the event.

Referenced from `STATUS.md` and `DECISIONS.md` by phase.

| Phase | What was reused | Source | Notes |
|---|---|---|---|
| — | Dashboard UI shell (layout, base components) | InvenSight, pre-hackathon | Partial build before the event; extended, not rebuilt. See `HACKATHON-CONTEXT.md` |
| — | ML model (markdown/pricing) | InvenSight, pre-hackathon prototype | **Not reused as working code** — required full retraining against a new objective, treated as new work for this event |
| Phase 8 | CSV import pattern & seed generator structure | Adapted from Phase 1 (`inventory.py`) & Phase 0 (`seed.py`) | Reused standard library `csv.DictReader` pattern and SQLAlchemy engine context management |

---

## AI-assistance disclosure

<Fill in per the hackathon's specific disclosure requirements —
what was AI-assisted (code generation, architecture planning,
documentation) vs. team-authored.>
