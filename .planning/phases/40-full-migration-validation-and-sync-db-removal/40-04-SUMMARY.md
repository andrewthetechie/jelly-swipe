---
phase: 40-full-migration-validation-and-sync-db-removal
plan: 04
subsystem: ci-docs
tags: [VAL-04, requirements, validation, guard-script]

requires:
  - plan: "40-03"
    provides: Application package free of banned sync SQLite surface targeted by scans.
provides:
  - Executable `scripts/phase40_val04_guard.sh` scoped strictly to **`jellyswipe/*.py`**
  - CI step running guard before **`uv run pytest tests/`**
  - `40-VALIDATION.md` / `40-VERIFICATION.md` / ROADMAP sign-off linkage (D-16)
affects:
  - milestone: v2.1
    note: Requirement checkboxes and trace table already aligned in **`REQUIREMENTS.md`**.

tech-stack:
  added: []
  patterns:
    - `rg`-based denial list for sqlite3/import patterns, legacy helpers, SQLModel, and table-creating `init_db`

key-files:
  created:
    - scripts/phase40_val04_guard.sh
  modified:
    - .github/workflows/test.yml
    - .planning/REQUIREMENTS.md
    - .planning/phases/40-full-migration-validation-and-sync-db-removal/40-VALIDATION.md
    - .planning/phases/40-full-migration-validation-and-sync-db-removal/40-CONTEXT.md (D-12 deferred notes)

key-decisions:
  - "Fail CI if **`rg`** is missing (exit **2**) — workflow installs **`ripgrep`** on Ubuntu runners."

requirements-completed: [VAL-04]

duration: ~30min
completed: 2026-05-07
---

# Phase 40 — Plan 04 Summary

**Automate VAL-04 on `jellyswipe/` only, wire CI, and finish the validation / verification paperwork for milestone closure.**

## Performance

- **Artifacts:** Guard script + workflow step + `40-VALIDATION` / `40-VERIFICATION` updates (this closure commit).

## Accomplishments

- **`scripts/phase40_val04_guard.sh`** enforces bans: raw `sqlite3` imports/connect, `get_db_closing`, `SQLModel`, and `def init_db` under `jellyswipe/`.
- **`.github/workflows/test.yml`** runs the guard before the test suite; `apt` installs `ripgrep` because the script requires `rg`.
- **`REQUIREMENTS.md`** documents **ADB-03** / **VAL-02–04** complete with trace rows (from prior edit in this phase).

## Deferred (D-12)

**`DatabaseUnitOfWork.run_sync`** remains for **`AsyncSession.run_sync`** bridging — see **`40-CONTEXT.md`** `<deferred>` and **`40-VALIDATION.md`**.

---

*Phase: 40-full-migration-validation-and-sync-db-removal · Completed: 2026-05-07*
