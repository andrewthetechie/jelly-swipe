---
phase: "03"
plan: "01"
subsystem: backend
tags: [jellyfin, auth, factory]
key-files:
  - media_provider/jellyfin_library.py
  - media_provider/factory.py
---

# Plan 01 — Summary

## Outcome

Verified the existing Jellyfin server session path: `get_provider()` constructs `JellyfinLibraryProvider`, `ensure_authenticated()` performs API-key or `Users/AuthenticateByName` login, `_verify_items()` probes **`GET /Items`**, and `_api` performs a single **401 → `reset()` → re-auth → retry** cycle. No code changes were required beyond what was already on `main`.

## Deviations

None.

## Self-Check

PASSED — plan acceptance greps (`AuthenticateByName`, `_verify_items`, `401`) and `python -m py_compile media_provider/jellyfin_library.py media_provider/factory.py`.

**Plan verification (manual):** Full import with wrong Jellyfin creds is still influenced by repo `.env` via `python-dotenv`; use `env -i …` or stub `dotenv` when reproducing strict negative tests (same note as Phase 1 summaries).
