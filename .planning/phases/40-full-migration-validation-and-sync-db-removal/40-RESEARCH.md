# Phase 40 — Research (planner briefing)

**Gathered:** 2026-05-07  
**Scope:** Full migration validation (VAL-02), suite green (VAL-03), application-layer sync DB removal satisfying ADB-03 and VAL-04, after Phase 39 merge.

This document is input for **executable plans**: concrete file choices, ordering, and verification hooks.

---

## Requirements in play

| ID | Text (abridged) | Phase 40 implication |
|----|-----------------|---------------------|
| **ADB-03** | Application DB interactions use async SQLAlchemy APIs, not direct `sqlite3` connections. | Eliminate `sqlite3` usage under `jellyswipe/` (runtime). Any remaining “sync” work must be SQLAlchemy/driver-level (e.g. `run_sync` on the async session), not raw `sqlite3`. |
| **VAL-02** | Migration tests: empty DB reaches current schema; already-current DB stays upgrade-safe (idempotent). | New automated coverage: fresh file → `upgrade head` → assert schema; second pass / CLI idempotency per `40-CONTEXT.md` D-02 (subprocess Alembic encouraged). |
| **VAL-03** | Existing DB, auth, room, route, SSE, and security tests pass after the migration. | Full `pytest` gate; fixtures that still use `jellyswipe.db.get_db()` / `get_db_closing()` must be migrated or replaced when app module drops those APIs. |
| **VAL-04** | Source scan: no app-layer `sqlite3` DB usage, no table-creating `init_db()`, no SQLModel dependency. | Scripted or `rg`-based checks **scoped to `jellyswipe/`** only (D-05/D-06); `init_db()` is already absent from code — verify stays absent; SQLModel absent from deps and `jellyswipe/` (currently clear). |

`REQUIREMENTS.md` marks ADB-03, VAL-02, VAL-03, VAL-04 as Phase 40 and still unchecked until verification is proven at phase close (D-15).

---

## Risks

1. **`jellyswipe/migrations.py` ↔ `jellyswipe.db.DB_PATH` coupling.** `get_database_url()` reads `jellyswipe.db.DB_PATH` when env vars are unset. Removing or narrowing `db.py` without relocating this default-path resolution breaks Alembic URL resolution for scripts and tests that rely on implicit `DB_PATH`.

2. **Test suite hidden dependency on legacy sync helpers.** Many tests seed or inspect state via `jellyswipe.db.get_db()` or `get_db_closing()` (`tests/conftest.py` `db_connection`, `test_routes_room.py`, `test_routes_sse.py`, `test_routes_xss.py`, `test_error_handling.py`, plus auth/infra tests). Phase 40 cannot delete those symbols until each callsite uses async UoW, repositories, or SQLAlchemy Core on the managed async engine — otherwise VAL-03 regresses without any production bug.

3. **`cleanup_expired_auth_sessions` still uses sync `sqlite3`.** `jellyswipe/db.py` implements it with `get_db_closing()` and raw `DELETE`; async variants exist (`cleanup_expired_auth_sessions_async`). Callers must be switched before removing sync entry points.

4. **Duplicate maintenance paths.** `cleanup_orphan_swipes_async` vs `cleanup_orphan_swipes()`, `prepare_runtime_database_async` vs `prepare_runtime_database()` — planners must trace startup (`jellyswipe/__init__.py`, `bootstrap.py`) so only supported paths remain; dead sync wrappers drop with ADB-03.

5. **`run_sync` / PAR-04 vs ADB-03 wording.** `DatabaseUnitOfWork.run_sync` uses SQLAlchemy’s bridge, not Python `sqlite3`. If Phase 39 keeps swipe serialization there, Phase 40 still satisfies ADB-03 **if** raw `sqlite3` is gone from `jellyswipe/`. Document retention in `40-VALIDATION.md` if scanners or reviewers ask (see `40-CONTEXT.md` D-12, “specific ideas”).

6. **Subprocess Alembic tests** need a reliable `PYTHONPATH`/working directory and `alembic.ini` path identical to CI; flaky env differences are the main operational risk.

7. **Scope creep.** VAL-04 applies to **`jellyswipe/`** only — do not fail the gate on `tests/` or `alembic/` `sqlite3` (D-05/D-06).

---

## Current code touchpoints (inventory)

### Application package — **`jellyswipe/db.py`** (primary removal target)

- Imports **`sqlite3`**; exposes **`get_db`**, **`get_db_closing`**, **`configure_sqlite_connection`**.
- **`DB_PATH`** global mutated from `__init__.py` (testing) and patched widely in tests.
- **Async-aligned pieces** planners may **move** rather than delete: WAL/pragma helpers via async runtime (`ensure_sqlite_wal_mode`), maintenance orchestration (`prepare_runtime_database_async`, `cleanup_*_async`), thin sync `asyncio.run` wrappers.
- **`cleanup_expired_auth_sessions`** is still sync/`sqlite3`-based — high priority to replace.

### **`jellyswipe/migrations.py`**

- **`import jellyswipe.db`** for `DB_PATH` fallback in `get_database_url()`.

### **`jellyswipe/__init__.py`**

- Sets **`jellyswipe.db.DB_PATH`** from test config path when applicable.

### **`jellyswipe/db_runtime.py`** / **`jellyswipe/db_uow.py`**

- Canonical async runtime and UoW; **`run_sync`** lives on `DatabaseUnitOfWork` (PAR-04 bridge). Not the same class of problem as `sqlite3`.

### **`alembic/env.py`**

- Sync `create_engine` + migrations; uses `target_metadata` and **`jellyswipe.migrations.get_database_url`** pattern via Alembic config. Exempt from app-layer bans (D-06).

### **Baseline revision**

- Reference: `alembic/versions/0001_phase36_baseline.py` — expected “head” for parity checks.

### **Tests importing `jellyswipe.db`**

- **`tests/conftest.py`**: `_bootstrap_temp_db_runtime` patches `DB_PATH`; **`db_connection`** yields **`jellyswipe.db.get_db()`**.
- **`tests/test_db.py`**, **`tests/test_infrastructure.py`**: assert surface of `db` module including `get_db`, `get_db_closing`, maintenance functions; inspect source for forbidden patterns — will require rewrite when module shrinks.
- **`tests/test_routes_room.py`**, **`tests/test_routes_sse.py`**, **`tests/test_routes_xss.py`**, **`tests/test_error_handling.py`**: direct **`get_db()`** / **`get_db_closing()`** for fixtures or assertions.
- **`tests/test_auth.py`**, **`tests/test_dependencies.py`**, **`tests/test_db_runtime.py`**, repository/service tests: **`DB_PATH`** monkeypatch pattern.

### **Production code**

- Router/services in `jellyswipe/` should already be on `db_runtime` / `db_uow` post–Phase 39 for hot paths; grep shows **no** `get_db_closing` in `jellyswipe/` outside **`db.py`**. Sync removal is **`db.py` + test fallout + migrations URL fallback**.

---

## Alembic and test patterns (what already works)

| Pattern | Location | Use for Phase 40 |
|---------|----------|------------------|
| Temp DB URL + programmatic upgrade | `jellyswipe.migrations.upgrade_to_head`, `build_sqlite_url`, `normalize_sync_database_url` | Baseline for VAL-02 “empty → head”; can remain in-process for first assertion. |
| Async runtime binding after migrate | `build_async_sqlite_url` + `initialize_runtime` | Already in `tests/conftest.py` `_bootstrap_temp_db_runtime`. |
| Full suite driver | `pyproject.toml` `[tool.pytest.ini_options]` — **`uv run pytest`** | VAL-03 gate (project uses `uv`; addopts include coverage). |
| **`db_path` fixture** | `tests/conftest.py` | Isolate migration parity tests with fresh files under `tmp_path`. |

**Gap:** there is **no** dedicated migration parity test module today (`rg` over `tests` found none). VAL-02 is net-new automation.

---

## Removal strategy for `jellyswipe/db.py`

Recommended sequencing for planners:

1. **After Phase 39 merge** — **D-09** (no speculative deletion).

2. **Replace remaining sync maintenance** — Point `cleanup_expired_auth_sessions` callers at **`cleanup_expired_auth_sessions_async`** (or lifespan-only async path already used elsewhere); drop sync body using `get_db_closing`.

3. **Decouple URL resolution from `db.DB_PATH`** — Move default path / “module-level DB path holder” into a neutral module (**`jellyswipe/migrations.py`**, **`jellyswipe/config.py`**, or a tiny **`jellyswipe/db_paths.py`**) so `get_database_url()` does not import a deprecated `sqlite3` module.

4. **Migrate test helpers off `get_db` / `get_db_closing`** — Prefer **`DatabaseUnitOfWork`** + **`get_sessionmaker()`** inside `asyncio.run` for tests that must touch SQL, or use repository factories shared with Phase 39 tests (`test_repositories`-style bootstrap already patches `DB_PATH`).

5. **Shrink or delete `db.py`** — Either full removal (**D-10**) or a **small residue** exporting only **`DB_PATH` compatibility**, re-exports of async helpers, or constants (**no** `sqlite3`).

6. **Preserve `ensure_sqlite_wal_mode` / startup maintenance** behavior via async-only entry points documented in **`40-VALIDATION.md`** if signatures move.

---

## Validation Architecture

Nyquist-aligned validation is **enabled** for this workspace (`.planning/config.json`: `"nyquist_validation": true`). Phase 40’s canonical artifact is **`40-VALIDATION.md`** (same family as **`39-VALIDATION.md`**): requirement → evidence matrix, sampling rules, Wave 0 preconditions, and sign-off checklist including roadmap traceability (**D-13, D-16**).

### Commands

| Intent | Command |
|--------|---------|
| **Quick dependency / UoW smoke** (reuse established micro-smoke from Phase 39 style) | `uv run pytest tests/test_dependencies.py::TestGetDbUow::test_yields_uow_and_commits_on_success -q` |
| **Focused migration parity slice** (once tests exist — planner-defined node) | Planner should attach the smallest `pytest` node covering VAL-02, e.g. `uv run pytest tests/test_migrations.py -q` or `tests/test_db.py`-scoped migration tests |
| **Full suite (VAL-03)** | `uv run pytest` |
| **Phase-40-ish domain regression batch** | After edits touching routes/SSE/security: something like `uv run pytest tests/test_routes_room.py tests/test_routes_sse.py tests/test_route_authorization.py tests/test_routes_xss.py tests/test_error_handling.py tests/test_dependencies.py -x` |

### Sampling (Nyquist continuity)

Mirror Phase 39’s rhythm; adapt labels to Phase 40 work:

- **After each substantive task commit:** quick smoke (`test_dependencies` UoW test above) **plus** either the migration parity node **or** one file touched by VAL-04-relevant edits (alternate to avoid stale migration coverage — keep **≤~25 s** smoke budget where possible per Phase 39 template).
- **After each plan wave:** broader pytest batch (migration module + routing/SSE/security slice) **before** wave sign-off.
- **Before milestone / verify-work / phase close:** full `uv run pytest` (**VAL-03**).
- **VAL-04:** run the agreed grep/script gate on **`jellyswipe/`** at phase end and optionally on sensitive PR commits (CI integration is planner’s **D-11** choice).

### Wave 0 (blocking prerequisites before implementation waves earn credit)

Treat Wave 0 as “evidence and harness exist before feature deletion”:

- [ ] **`40-VALIDATION.md`** drafted with frontmatter (`nyquist_compliant`, `wave_0_complete`) and rows for **ADB-03, VAL-02, VAL-03, VAL-04** mapping to concrete file/CI evidence.
- [ ] **VAL-02 automated tests** committed or stubbed with failing tests **skipped with explicit TODO** only if plans forbid TDD — default is **new tests present** (empty DB → head; idempotent upgrade via **subprocess** `alembic upgrade head` per **D-02**, plus table presence or `alembic_version` assertions per **D-04**).
- [ ] **`rg`/`ast-grep`/script inventory** documented for VAL-04 (patterns: `import sqlite3`, `get_db_closing`, `sqlite3.connect`, forbidden `SQLModel`, and `init_db` table-creation resurrection) — restricted to **`jellyswipe/`**.
- [ ] Call out **explicitly** in Wave 0 if **`run_sync`** remains — link to **`40-VALIDATION.md`** “deferred / technical debt” subsection so D-12 does not silently diverge (**40-CONTEXT**).

Until Wave 0 is satisfied, downstream task rows in **`40-VALIDATION.md`** should mark automated verify targets as **`❌ W0`** like Phase 39’s template.

---

## Planner checklist (executable outcomes)

1. Decide **`db.py`**: delete vs residue module (**D-10**) and where **`DB_PATH`** / `get_database_url` fallback lives post-removal.

2. Add **VAL-02** tests + fixtures (temp DB, subprocess Alembic per **D-02**).

3. Rewire **all** tests off `get_db` / `get_db_closing` / `sqlite3`-level assertions tied to **`jellyswipe.db`**.

4. Define **VAL-04** enforcement in CI or `justfile`/`Makefile` (**D-11**).

5. Close with **`40-VALIDATION.md`** sign-off and **then** update **`REQUIREMENTS.md`** checkboxes (**D-15**).

---

## RESEARCH COMPLETE
