# RULE.md — InvenSight working rules

These rules apply to every contributor — human or coding agent — working on this repository, across both the original liquidation/redistribution build (Phases 0-7) and the demand forecasting extension (Phases 8-13). Read this file before writing the first line of code in any session.

---

## 1. Work strictly phase by phase

- Only one phase is "active" at a time. Do not begin work on a later phase's deliverables while an earlier phase is incomplete, and do not pull in scope from a future phase "while you're in there."
- If you notice something in a later phase that would be easier to address now, **do not act on it** — note it in `DECISIONS.md` under the current phase, and revisit it when that phase actually starts.
- Each phase has a defined deliverable and a defined "definition of done" (see the playbook chapters for each phase's specific criteria). Do not mark a phase complete until that definition is actually met and verified — not assumed, not "should work."
- Scope discipline applies especially hard to the existing, working Phase 0-7 code once Phase 8+ begins: **do not edit, refactor, or "clean up" already-working files from earlier phases as a side effect of building a new one.** New phases are additive (new tables, new routers, new dashboard tabs) specifically so this is never necessary. If a new phase seems to require changing old code, stop and flag it rather than proceeding.

## 2. One branch per phase, with frequent commits

- Every phase gets its own branch, named `phase-N-short-description` (e.g. `phase-8-sales-history`, `phase-9-forecasting-model`).
- Commit small and often within a phase branch — every meaningful, working increment gets its own commit, not one giant commit at the end of the phase. A good rule of thumb: if you could describe what changed in one clear sentence, it's a commit.
- Never commit directly to `main` or `dev`. All work lands there through the merge step described in Rule 3.
- Never commit secrets, real API keys, or `.env` (or any `.env.*` variant containing real values, including backup files like `.env.save`) — verify `git status` before every commit shows nothing sensitive staged.

## 3. Explicit permission required before pushing or starting a new phase

- Before running `git push` for the first time on a new branch, or before merging a phase branch into `dev`/`main`, **explicitly ask for confirmation** and wait for an explicit go-ahead. Do not push preemptively "to be safe" or "to back up progress" — local commits are the backup; pushing is a deliberate, confirmed action.
- Before beginning work on a new phase (starting a new branch, writing the first line of that phase's code), **explicitly ask for confirmation** that the previous phase is genuinely done and that starting the next one is wanted now, rather than assuming and proceeding.
- If asked to "just keep going" across multiple phases in one sitting, still pause at each phase boundary to confirm — a standing "yes" from earlier in a session is not the same as confirmation at the actual boundary, since scope and priorities can shift mid-session.

## 4. Continuous documentation — every phase, every commit boundary

Two files carry the project's memory across sessions and across contributors (human or agent). Both must be updated at every phase boundary, and ideally at every meaningful commit:

### `STATUS.md`
Tracks, per phase:
- **What's built** — concretely, not aspirationally (e.g. "POST /batches endpoint live and tested" not "working on batch endpoints")
- **What's in progress** — the current, active piece of work
- **What's left** — remaining deliverables for the current phase, and a reference to which future phase covers anything explicitly deferred

### `DECISIONS.md`
Tracks, per phase:
- Every non-trivial technical decision made and **why** — e.g. "chose GradientBoostingRegressor with quantile loss for confidence bands over a separate quantile regression library, to avoid a new dependency under time pressure (see playbook Ch. 10.3)"
- Anything explicitly deferred to a later phase (cross-reference Rule 1's scope discipline) and which phase it's deferred to
- Any deviation from the playbook's original plan, and the reasoning

**The test for both files**: a new contributor — human or a fresh agent session with no prior context — should be able to read `STATUS.md` and `DECISIONS.md` and pick up work immediately, without needing to read the entire chat history or reverse-engineer intent from the code alone. If a new reader would have to ask "wait, why was it built this way," that question's answer belongs in `DECISIONS.md` and is currently missing.

## 5. Cite sources and inspiration — a standing practice, not a one-time disclosure

- Every reused piece of code, design pattern, dashboard component, or third-party integration approach is logged in `SOURCES.md` **at the time it's used**, not reconstructed retroactively before submission. Anything genuinely built fresh during the hackathon window gets no entry — this file only tracks what is *not* original to the event.
- Every `DECISIONS.md` entry includes a source field: **"original to this hackathon"** or **"adapted from `<specific source>`"** — provenance is part of the decision record, not a separate afterthought.
- Where AI tools were used in the build (code generation, architecture planning, this playbook itself), check the specific hackathon's AI-assistance disclosure rules and prepare an accurate statement of what was AI-assisted vs. team-authored. This is a separate check from general code-reuse disclosure and is easy to miss if only one is verified.
- Before submission, do a final pass over both `SOURCES.md` and `DECISIONS.md` for accuracy — the goal is that any judge question about origin or authorship can be answered by pointing at a specific line in a specific file, not from memory.

## 6. Repository authenticity — commit history stays real

- When continuing a project that predates the hackathon, the repository's commit history is carried over intact — real commits, real original timestamps, never rewritten or backdated to obscure what predates the event window.
- A `HACKATHON-CONTEXT.md` file at the repo root states plainly, in the team's own words, what existed before the event and what was built during it — created once, at the start, and never edited to retroactively claim more than what's true.
- If a hackathon's rules restrict use of pre-existing work, confirm the specific policy with organizers before relying on any pre-existing asset, and document the confirmation received.

---

## How these rules apply across the two volumes

Phases 0-7 (original playbook) and Phases 8-13 (demand forecasting extension) are one continuous project under one `STATUS.md` and one `DECISIONS.md` — not two separate documentation sets. When Phase 8 begins, `STATUS.md` should already reflect Phases 0-1 as done and Phases 2-7 as planned/in-progress/not-started per their actual state — Phase 8 does not get a fresh file that loses that history.
