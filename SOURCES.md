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
| Phase 9 | `HistGradientBoostingRegressor` with quantile loss | Scikit-Learn documentation (`sklearn.ensemble.HistGradientBoostingRegressor`) | Model class and `loss="quantile"` API — original application to demand forecasting in this codebase |
| Phase 9 | Time-based train/validation split pattern | Standard ML best practice (temporal causality) | No specific source; applied from general ML discipline |
| Phase 10 | Safety stock formula structure | Adapted from standard inventory management literature (EOQ / safety stock buffer concept) | Formula itself (`predicted_demand * base_pct * (2.0 - confidence)`) is original to this project |
| Phase 11 | Chart.js multi-series line chart | Chart.js documentation (https://www.chartjs.org/docs/) | Original chart configuration, dataset labels, and dynamic theme color switching |
| Phase 12 | Closed-loop underperformance detection logic | Original to this hackathon | No prior art reused — logic, threshold (70%), and boost (+0.25) are original design decisions |
| Phase 13 | Demo script structure | InvenSight Playbook Vol. II Ch. 14.1 | Extended run-of-show sequence follows playbook chapter; narration is original |

---

## AI-assistance disclosure

This project used AI coding assistance (Antigravity/Claude) throughout the hackathon window for:
- Architecture planning and phase-by-phase implementation guidance
- Code generation for backend services, API routes, ML pipeline components, and test suites
- Documentation drafting (DECISIONS.md, STATUS.md, DEMO_SCRIPT.md, QA_PREP.md)

The **design decisions**, **problem framing**, **feature prioritisation**, and **all final review/approval** of generated code were made by the team. The AI assistant acted as a pair-programmer, not an autonomous author. All generated code was reviewed, tested (51 automated tests), and integrated by the team.

Check your specific hackathon's AI-assistance disclosure policy and supplement this statement with any required platform-specific wording.

