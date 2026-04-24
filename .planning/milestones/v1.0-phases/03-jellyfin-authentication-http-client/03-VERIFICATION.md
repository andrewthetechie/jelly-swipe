---
phase: 3
status: complete
verified: 2026-04-24
---

# Phase 3 verification (JAUTH-01 — JAUTH-03)

Server-side Jellyfin session: env contract, token acquisition, `/Items` probe, and safe error surfaces. Evidence uses **Flask `app.test_client()`** under a clean environment (`env -i PATH HOME …`) with **dummy** credentials and **no** Jellyfin listener unless noted.

## Traceability

| Requirement | Status | Evidence summary | Date |
|-------------|--------|------------------|------|
| JAUTH-01 | PASS | `app.py` validates `JELLYFIN_URL` plus either API key **or** username + credential pair; `JellyfinLibraryProvider._login_from_env` implements both branches. | 2026-04-24 |
| JAUTH-02 | PARTIAL | `ensure_authenticated` → `_login_from_env` → `_verify_items` chain is live; token cleared in `reset()`. Full happy-path token reuse against a live server not re-run here (connection refused on `/Items` probe with dummy host). | 2026-04-24 |
| JAUTH-03 | PASS | Representative JSON errors from `test_client` calls contain **no** server access token substrings from env (see §Secrets checks). | 2026-04-24 |

## JAUTH-01 — Env contract (code + startup)

**Code references:** `app.py` Jellyfin startup validation (requires non-empty `JELLYFIN_URL` and one auth bundle); `media_provider/jellyfin_library.py` `_login_from_env` chooses API key vs `AuthenticateByName` POST.

**Live import smoke (no listener on Jellyfin port):**

```bash
env -i PATH="$PATH" HOME="$HOME" \
  MEDIA_PROVIDER=jellyfin \
  JELLYFIN_URL=http://127.0.0.1:8096 \
  FLASK_SECRET=dummy TMDB_API_KEY=dummy \
  python -c "import os; from app import app; print('import_ok', app.name)"
```

Observed: `import_ok app` (Flask app constructs; provider not touched until routes call `get_provider()`).

## JAUTH-02 — Token lifecycle

**Reset behavior:** `JellyfinLibraryProvider.reset()` clears `_access_token`, cached user/library ids, and rebuilds `requests.Session` (`jellyfin_library.py`).

**First provider use with unreachable host:** `GET /plex/server-info` via `test_client` returns HTTP **500** with JSON `{"error": "...Connection refused..."}` after auth probe fails — confirms fail-fast path without silent partial auth state surfacing as 200.

## JAUTH-03 — No secrets in logs / JSON

**Procedure:** `test_client` with `MEDIA_PROVIDER=jellyfin`, `JELLYFIN_URL=http://127.0.0.1:8096`, server key env set to literal `dummy` (not a real secret), `FLASK_SECRET` and `TMDB_API_KEY` set to `dummy`.

**Sample outcomes:**

- `GET /plex/server-info` → `500`, JSON `error` explains connection failure; body does **not** contain the literal `dummy` API key value from env in the JSON keys inspected manually.
- `POST /auth/jellyfin-login` with empty JSON fields → `400`, generic error key in JSON (route validates username + credential pair before upstream call).

**Secrets substring audit on this file:** run the negative `grep` from `07-01-PLAN.md` acceptance against this path; expect exit code **1** (no forbidden literals pasted into verification prose).
