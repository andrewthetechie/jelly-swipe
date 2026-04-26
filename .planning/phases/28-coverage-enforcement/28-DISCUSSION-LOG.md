# Phase 28: Coverage Enforcement - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in 28-CONTEXT.md — this log preserves the discussion.

**Date:** 2026-04-26
**Phase:** 28-coverage-enforcement
**Mode:** discuss

## Gray Areas Presented

1. **Threshold scope** — Whole-package vs per-file `__init__.py` enforcement
2. **Coverage configuration** — Append to addopts vs separate coverage section
3. **CI verification** — Whether CI workflow needs changes

## Decisions

All areas resolved with default/recommended choices — no interactive discussion needed.

| Area | Decision | Rationale |
|------|----------|-----------|
| Threshold scope | Whole-package `--cov-fail-under=70` | Currently 75% total; simpler than per-file; `__init__.py` at 78% dominates |
| Coverage configuration | Append to existing addopts | Single-line change to pyproject.toml; no new config sections |
| CI verification | No changes needed | CI runs `uv run pytest tests/` which reads pyproject.toml |

## Current Coverage Baseline

```
jellyswipe/__init__.py:          78%
jellyswipe/base.py:             100%
jellyswipe/db.py:                87%
jellyswipe/jellyfin_library.py:  69%
TOTAL:                           75%
Tests: 159 passing
```
