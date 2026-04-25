---
status: passed
phase: "10"
verified: 2026-04-24
---

# Phase 10 — Verification

## Must-haves (Plan 01)

| Criterion | Evidence |
|-----------|----------|
| `pyproject.toml` with `name = "jellyswipe"` | `grep -q 'name = "jellyswipe"' pyproject.toml` — PASS |
| `requires-python = ">=3.13,<3.14"` | `grep` on `pyproject.toml` — PASS |
| `uv.lock` present | `test -f uv.lock` — PASS |
| `.python-version` is `3.13` | `grep -qx '3.13' .python-version` — PASS |

## Must-haves (Plan 02)

| Criterion | Evidence |
|-----------|----------|
| `uv sync` on 3.13 | `uv sync --python 3.13` — PASS |
| `py_compile` on `app.py` and `media_provider/*.py` | `uv run python -m py_compile …` — PASS |
| `requirements.txt` deprecation line | `head -n 1` starts with `# Deprecated for local dev:` — PASS |

## Optional

- Import smoke: `uv run python -c "import flask, plexapi, werkzeug, requests, dotenv, gunicorn"` — PASS

## human_verification

None required for this tooling phase.

## Gaps

None.
