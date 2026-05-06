---
phase: 36-alembic-baseline-and-sqlalchemy-models
plan: 01
subsystem: persistence
tags: [SQLAlchemy, declarative-models, metadata, Alembic]

requires:
  - phase: 35
    provides: FastAPI package layout and current sync persistence behavior
provides:
  - SQLAlchemy and Alembic dependencies
  - `jellyswipe.models` package with schema-only declarative models
  - pure metadata assembly module for Alembic
  - lazy package-root app export so metadata imports no longer trigger app startup
affects: [36, 37, 38, 39, 40]

tech-stack:
  added: [sqlalchemy, alembic]
  patterns: [schema-only model modules, pure metadata import boundary, lazy package-root app export]

key-files:
  created:
    - jellyswipe/models/__init__.py
    - jellyswipe/models/base.py
    - jellyswipe/models/room.py
    - jellyswipe/models/swipe.py
    - jellyswipe/models/match.py
    - jellyswipe/models/auth_session.py
    - jellyswipe/models/metadata.py
    - tests/test_models_metadata.py
  modified:
    - pyproject.toml
    - uv.lock
    - jellyswipe/__init__.py
    - jellyswipe/dependencies.py

key-decisions:
  - "Keep room/swipe/match table names stable in Phase 36; apply the bounded rename only to user_tokens -> auth_sessions"
  - "Use ORM mapper primary keys for keyless legacy tables instead of inventing new database primary keys in the baseline"
  - "Remove package-root app startup side effects by lazy-loading `jellyswipe.app` via `__getattr__`"

patterns-established:
  - "Pattern 1: Alembic imports `jellyswipe.models.metadata`, not package-root app wiring"
  - "Pattern 2: keyless SQLite tables can stay keyless in DDL while ORM identity is defined with `__mapper_args__`"
  - "Pattern 3: provider singleton access should go through `jellyswipe.config`, not `jellyswipe.__init__` side effects"

requirements-completed: [SCH-01, SCH-02, SCH-03, MIG-03]
completed: 2026-05-05T19:20:00Z
---

# Phase 36 Plan 1 Summary

Added the SQLAlchemy foundation for the persistence migration. The repo now has a dedicated `jellyswipe.models` package, a pure metadata assembly module, and focused metadata tests. I also removed the package-root app startup side effect that would have made `jellyswipe.models.metadata` unusable from Alembic.

## Verification

- `uv run python -c "from jellyswipe.models.metadata import target_metadata; print(sorted(target_metadata.tables.keys()))"`
- `uv run pytest tests/test_models_metadata.py -q --no-cov`
- `rg -n "sqlmodel|SQLModel" pyproject.toml jellyswipe tests` returned no matches

## Notes

- `user_tokens` is represented as `auth_sessions` in the new model layer.
- `matches` intentionally has no room FK because archived rows still use `room_code='HISTORY'`.
- The lazy `jellyswipe:app` export keeps deployment compatibility while making metadata imports side-effect free.
