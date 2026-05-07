---
phase: 40
slug: full-migration-validation-and-sync-db-removal
status: draft
nyquist_compliant: true
wave_0_complete: false
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
| **Quick run command** | `uv run pytest tests/test_dependencies.py::TestGetDbUow::test_yields_uow_and_commits_on_success -q` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | ~30s smoke / ~120s+ full with coverage |

---

## Sampling Rate

- **After every task commit:** Quick smoke above + any new migration test file touched
- **After every plan wave:** `uv run pytest` (full suite preferred before merge)
- **Before `/gsd-verify-work`:** Full suite green
- **Max feedback latency:** 30s for per-task smoke where possible

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| T-40-01-mig | 01 | 1 | VAL-02 | T-40-01 | Migration commands do not mutate operator data paths unexpectedly. | integration | `uv run pytest tests/test_migrations.py -q` | `tests/test_migrations.py` | ✅ green |
| *Planned* | 02 | 2 | ADB-03, VAL-03 | T-40-02 | No runtime route regresses auth/room/SSE contracts when sync DB helpers go away. | route + unit | `uv run pytest` *(subset then full)* | ✅ | ⬜ pending |
| *Planned* | 03 | 3 | VAL-04 | T-40-03 | Scans only flag true app-layer violations under `jellyswipe/`. | script / grep | `uv run pytest` + VAL-04 script *(plan defines)* | ✅ | ⬜ pending |
| *Planned* | 04 | 4 | ADB-03..VAL-04 | — | Planning sign-off + REQ checkboxes + deferred work recorded. | docs | Manual review + checklist in this file | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

> **Note:** Task IDs and plan/wave columns are filled precisely by PLAN.md tasks during execution (Nyquist derivations).

---

## Wave 0 Requirements

- [ ] New or extended tests proving **empty DB → Alembic upgrade head** and **idempotent** second upgrade (subprocess Alembic preferred per `40-CONTEXT.md` D-02).
- [ ] **`jellyswipe/`** free of `sqlite3` imports / `get_db_closing` / table-creating legacy paths (except any explicitly documented residue per D-10).
- [ ] Test suite migrated off `jellyswipe.db.get_db` / `get_db_closing` where those APIs are removed (VAL-03).
- [ ] VAL-04 enforcement script or documented `rg` gate scoped to `jellyswipe/` only.

*If Wave 0 resolves to “existing coverage only,” executor updates this list to match RESEARCH.*

---

## Deferred / intentionally out of scope (must stay in sync with `40-CONTEXT.md` `<deferred>`)

| Item | Reason | Tracked in |
|------|--------|------------|
| *None yet* | Populate during execution if D-12 retains `run_sync` or similar | This section + CONTEXT |

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| None expected | — | Phase 40 is automation-heavy (migrations + suite + scan) | N/A |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s for per-task smoke where applicable
- [x] `nyquist_compliant: true` set in frontmatter
- [ ] ROADMAP Phase 40 success criteria (1–4) explicitly checked in executor notes

**Approval:** pending
