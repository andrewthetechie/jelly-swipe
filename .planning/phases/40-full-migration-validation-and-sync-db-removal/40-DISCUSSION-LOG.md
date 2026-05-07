# Phase 40: Full Migration Validation and Sync DB Removal - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `40-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-05-07
**Phase:** 40-full-migration-validation-and-sync-db-removal
**Areas discussed:** Migration parity tests (VAL-02), VAL-04 application-layer boundary, Legacy removal sequencing, Planning verification record

**Note:** Areas 1–3 were captured in `40-DISCUSS-CHECKPOINT.json` on 2026-05-06; session resumed 2026-05-07 and Area 4 was closed.

---

## Migration parity tests (VAL-02)

| # | Question | Options (summary) | Selected |
|---|----------|-------------------|----------|
| 1 | Where should VAL-02 tests primarily live? | A new focused module / extend existing migration file / planner chooses minimal duplication | **C** — planner chooses minimal duplication with existing conftest Alembic bootstrap |
| 2 | How should already-at-head idempotency be asserted? | Programmatic twice / subprocess CLI / both | **B** — subprocess Alembic CLI (mirrors ops) |
| 3 | Share temp DB/settings with route tests? | Same conftest / isolated fixture / planner decides | **B** — isolated fixture for clarity/speed |
| 4 | Empty-database proof minimum bar? | Table presence / + version row / + smoke query | **A** — fresh file DB + upgrade head + table presence |

**Notes:** Checkpoint Q&A verbatim from resumed JSON.

---

## VAL-04 application-layer boundary

| # | Question | Options (summary) | Selected |
|---|----------|-------------------|----------|
| 1 | Scope of no-`sqlite3` rule? | `jellyswipe/` only / + tests / planner decides | **A** — `jellyswipe/` only |
| 2 | Alembic revision scripts and env.py? | Allowed in alembic/ / zero raw sqlite3 / planner decides | **A** — allowed in toolchain; ban targets runtime app |
| 3 | `init_db()` / legacy DDL? | Remove table-creating paths / symbol must not exist / planner decides | **A** — remove table-creating paths |
| 4 | SQLModel? | Zero repo-wide / `jellyswipe/` only / planner decides | **B** — zero in `jellyswipe/` |

---

## Legacy removal sequencing

| # | Question | Options (summary) | Selected |
|---|----------|-------------------|----------|
| 1 | Sequencing vs Phase 39? | After 39 merged / overlap with stubs / planner decides | **A** — start after Phase 39 merged |
| 2 | Trim `jellyswipe/db.py`? | Delete / small utils module / planner decides | **C** — planner decides |
| 3 | CI gate before Phase 40 done? | pytest only / pytest + grep/script / planner decides minimal | **C** — planner decides |
| 4 | `run_sync()` bridge? | Keep if needed / must eliminate / planner decides | **C** — planner decides |

---

## Planning verification record

| # | Question | Options considered | Selected |
|---|----------|------------------|----------|
| 1 | Canonical artifact for milestone verification? | Separate doc vs CONTEXT-only vs Nyquist VALIDATION sibling | **`40-VALIDATION.md`** in phase dir (mirror Phase 39 family) |
| 2 | Where do intentional deferrals land? | VALIDATION-only / CONTEXT-only / both | **Both** `40-VALIDATION.md` subsection **and** `40-CONTEXT.md` `<deferred>` |
| 3 | When do REQUIREMENTS.md checkboxes flip? | Ad hoc / tied to VALIDATION sign-off | **At phase close**, driven by VALIDATION evidence |
| 4 | Roadmap success criterion 4? | Narrative appendix / matrix + sign-off in VALIDATION | **Explicit VALIDATION.md sign-off row** tying to roadmap criteria |

**User alignment:** Completed on resume (2026-05-07) without additional conversational turns; decisions match project Phase 39 validation pattern and ROADMAP success criterion 4.

---

## Claude's Discretion

- VAL-02 test module layout (D-01).
- Final shape of `jellyswipe/db.py` (D-10).
- CI gate composition for VAL-03 + VAL-04 (D-11).
- Fate of `run_sync()` / `BEGIN IMMEDIATE` bridge (D-12).

## Deferred Ideas

None recorded in checkpoint or final session.
