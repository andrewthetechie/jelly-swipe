---
phase: "04"
plan: "03"
subsystem: backend
tags: [jellyfin, tmdb, gap-closure]
key-files:
  - media_provider/jellyfin_library.py
  - app.py
---

# Plan 03 — Summary

## Outcome

Closed the UAT gap for trailer/cast 500 behavior by hardening Jellyfin TMDB item resolution. `resolve_item_for_tmdb()` now falls back to `/Users/{userId}/Items/{id}` when `/Items/{id}` fails, then raises a controlled `Jellyfin item lookup failed` error if lookup still cannot resolve title metadata. `/get-trailer/<movie_id>` and `/cast/<movie_id>` now map that known lookup failure to `404` with a stable user-facing error instead of opaque `500`.

## Deviations

Manual endpoint retest against the exact failing runtime item id still requires running app+Jellyfin locally, so this summary includes an automated fallback-path verification harness rather than live HTTP output.

## Self-Check

PASSED — `python -m py_compile media_provider/jellyfin_library.py app.py`; fallback lookup harness confirms `/Items/{id}` failure triggers `/Users/{uid}/Items/{id}` retry; route checks confirm `Movie metadata not found` 404 handling for trailer/cast lookup misses.
