# Research summary — Jellyfin milestone

**Synthesized:** 2026-04-22

## Stack

- Stay on Flask + `requests`; optionally add `jellyfin-apiclient-python` after a quick compatibility check. Prefer modern Jellyfin **`Authorization: MediaBrowser ...`** auth over legacy token headers where possible.

## Table stakes

- Token-based server auth, movies library queries, genre filtering, poster pipeline through the app, stable IDs for the existing swipe/match flow.

## Architecture

- Introduce a **single active media provider** behind a small interface; keep TMDB as downstream enrichment from title/year.

## Watch outs

- Legacy header disablement, `/proxy` path rules, genre mapping differences, and **strict env validation** so Jellyfin-only installs do not require Plex variables.

## Files

- `STACK.md`, `FEATURES.md`, `ARCHITECTURE.md`, `PITFALLS.md` — detail dimensions above.

---
*Research summary for Jellyfin milestone*
