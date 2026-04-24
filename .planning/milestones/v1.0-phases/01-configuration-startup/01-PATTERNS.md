# Phase 1 — Pattern map

## `app.py` (modify)

- **Role:** Flask app + env + Plex integration.
- **Analog:** Existing `required` / `missing` / `RuntimeError` block (lines ~18–21).
- **Pattern:** Keep fail-fast at import; extend to provider-conditional lists only (no new settings framework).

## `README.md` (modify)

- **Role:** Operator deployment reference.
- **Analog:** Existing TMDB / Docker sections; same tone and structure.

## `docker-compose.yml` (modify)

- **Role:** Example env wiring.
- **Analog:** Current `environment` list for Plex; add comments only unless vars are required for local dev defaults.
