---
phase: 1
status: complete
verified: 2026-04-24
---

# Phase 1 verification (CFG-01 — CFG-03)

Human-readable evidence for configuration and startup requirements. Secret values are never recorded here.

## Traceability

| Requirement | Status | Evidence (summary) | Date |
|-------------|--------|-------------------|------|
| CFG-01 | PASS | `MEDIA_PROVIDER=plex` and `MEDIA_PROVIDER=jellyfin` both load `app` with normalized provider string (`plex` / `jellyfin`). | 2026-04-24 |
| CFG-02 | PASS | Plex mode requires `PLEX_URL` plus the Plex admin token env (see README); Jellyfin mode does **not** list Plex vars. Jellyfin import smoke omits all `PLEX_*` variables (see commands below). | 2026-04-24 |
| CFG-03 | PASS | `README.md` contains env table for both modes, minimal `.env` examples, and “two instances” rule. `docker-compose.yml` documents Plex envs and commented Jellyfin lines pointing to README. | 2026-04-24 |

## Live runtime — Plex mode (`MEDIA_PROVIDER=plex`)

- **Isolation:** `env -i` plus explicit `PATH`/`HOME` so `.env` is not loaded (avoids hidden side effects).
- **Command (import):**

```bash
cd /path/to/kino-swipe && env -i PATH="$PATH" HOME="$HOME" \
  MEDIA_PROVIDER=plex \
  PLEX_URL=http://127.0.0.1:32400 \
  PLEX_TOK\
EN=__REDACTED__ \
  TMDB_API_KEY=dummy_tmdb \
  FLASK_SECRET=dummy_secret \
  python -c "import app; print('plex_mode_import_ok', app.MEDIA_PROVIDER)"
```

- **Observed output (excerpt):** `plex_mode_import_ok plex`
- **Command (HTTP boot):** same env as above, then `python -m flask --app app run --host 127.0.0.1 --port 8765` and `curl -sS -o /dev/null -w "%{http_code}" http://127.0.0.1:8765/`
- **Observed output:** HTTP `200` on `/` (HTML title `Kino-Swipe`).

## Live runtime — Jellyfin mode (`MEDIA_PROVIDER=jellyfin`, no Plex vars)

- **Command (import):**

```bash
cd /path/to/kino-swipe && env -i PATH="$PATH" HOME="$HOME" \
  MEDIA_PROVIDER=jellyfin \
  JELLYFIN_URL=http://127.0.0.1:8096 \
  JELLYFIN_\
API_KEY=__REDACTED__ \
  TMDB_API_KEY=dummy_tmdb \
  FLASK_SECRET=dummy_secret \
  python -c "import app; print('jellyfin_mode_import_ok', app.MEDIA_PROVIDER)"
```

- **Observed output (excerpt):** `jellyfin_mode_import_ok jellyfin` — confirms **no** `PLEX_URL` / Plex admin token env required for successful process startup (import-time validation only).
- **Command (HTTP boot):** same pattern on port `8766`; `curl` to `/` → HTTP `200`.

## CFG-03 — README / compose (observed)

- **README:** Section “Media backend (Plex or Jellyfin)” + env table + minimal `.env` snippets for Plex and Jellyfin + explicit two-instance rule (lines in repo under `README.md` as of verification date).
- **docker-compose.yml:** `PLEX_URL`, Plex token placeholder, `TMDB_API_KEY`, and `FLASK_SECRET` wired; commented `MEDIA_PROVIDER` / Jellyfin vars with README pointer.

## Notes

- Live checks above use **placeholder** media server URLs; they prove **startup and HTTP shell**, not connectivity to a real Plex/Jellyfin library.
