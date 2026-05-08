---
phase: 40
slug: full-migration-validation-and-sync-db-removal
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-07
---

# Phase 40 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.  
> Requirement coverage: **ADB-03**, **VAL-02**, **VAL-03**, **VAL-04**.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `pytest` (see `[tool.pytest.ini_options]` in `pyproject.toml`) |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/test_migrations.py -q` |
| **Full suite command** | `uv run pytest` |
| **VAL-04 guard** | `bash scripts/phase40_val04_guard.sh` |
| **Estimated runtime** | ~15s full suite (local) / CI + guard |

---

## Sampling Rate

- **After every task commit:** Guard script + targeted pytest where files touched
- **After every plan wave:** `uv run pytest` (full suite)
- **Before milestone sign-off:** Full suite + VAL-04 guard (recorded in `40-VERIFICATION.md`)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| T-40-01-mig | 01 | 1 | VAL-02 | T-40-01 | Migration commands do not mutate operator data paths unexpectedly. | integration | `uv run pytest tests/test_migrations.py -q` | `tests/test_migrations.py` | ✅ green |
| T-40-02-decouple | 02 | 2 | ADB-03, VAL-03 | T-40-02 | No route/auth/SSE contract regress when sync DB helpers disappear from harness. | route + unit | `uv run pytest` | tests + `jellyswipe/db_paths.py` | ✅ green |
| T-40-03-db-removal | 03 | 3 | ADB-03 | T-40-03 | Application package exposes no raw `sqlite3` app connector or legacy `get_db` seam. | unit + route | `uv run pytest` | `jellyswipe/db.py` | ✅ green |
| T-40-04-guard-ci | 04 | 4 | VAL-04 | T-40-04 | Scripted scan flags only true violations under `jellyswipe/`. | script | `bash scripts/phase40_val04_guard.sh` | `scripts/phase40_val04_guard.sh` | ✅ green |
| T-40-04-docs | 04 | 4 | ADB-03..VAL-04 | — | Planning sign-off + REQ checkboxes + deferred work recorded. | docs | Manual + `40-VERIFICATION.md` | `REQUIREMENTS.md` | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] New or extended tests proving **empty DB → Alembic upgrade head** and **idempotent** second upgrade (subprocess Alembic — `tests/test_migrations.py`, `alembic/env.py`).
- [x] **`jellyswipe/`** free of `import sqlite3` / `from sqlite3` / `sqlite3.connect`, `get_db_closing`, table-creating `def init_db`, and `SQLModel` per VAL-04 guard (`scripts/phase40_val04_guard.sh`).
- [x] Test suite migrated off `jellyswipe.db.get_db` / `get_db_closing` for application assertions (Plans 02–03).
- [x] VAL-04 enforcement via **`rg`** gate scoped to `jellyswipe/` only (**`alembic/`** explicitly out of scope per D-06).

---

## ROADMAP Phase 40 success criteria (D-16)

| # | Criterion | Evidence |
|---|-----------|----------|
| 1 | Migration tests prove empty-database upgrade to head and idempotent upgrade on an already-current database. | `tests/test_migrations.py`; subprocess `upgrade head` twice with `DATABASE_URL`. |
| 2 | Full local test suite passes after the persistence migration. | `uv run pytest` — **331 passed** (2026-05-07). |
| 3 | Source scan confirms application DB access no longer uses forbidden patterns in **`jellyswipe/`**. | `bash scripts/phase40_val04_guard.sh` — OK; CI runs same before pytest. |
| 4 | Planning verification records requirement coverage and intentionally deferred work. | `40-VERIFICATION.md`, `REQUIREMENTS.md`, deferred table below (`D-12`). |

---

## Deferred / intentionally out of scope (synced with `40-CONTEXT.md` `<deferred>`)

| Item | Reason | Tracked in |
|------|--------|------------|
| **`DatabaseUnitOfWork.run_sync`** | SQLAlchemy `AsyncSession.run_sync` bridge — not raw `sqlite3`; reassess when no callers need sync callbacks on the managed connection (**D-12**). | `40-CONTEXT.md` `<deferred>` + this table |

Alembic / migration toolchain may use sync SQLAlchemy against SQLite; VAL-04 scope is **`jellyswipe/*.py`** only.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| None blocking | — | Automation covers migrations, suite, and scan | N/A |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity maintained through plan waves
- [x] Wave 0 covers MISSING references for this milestone
- [x] No watch-mode flags introduced
- [x] `nyquist_compliant: true` set in frontmatter
- [x] ROADMAP Phase 40 success criteria (1–4) checked above

**Approval:** Phase 40 closed 2026-05-07 — see `40-VERIFICATION.md` for verifier notes.
