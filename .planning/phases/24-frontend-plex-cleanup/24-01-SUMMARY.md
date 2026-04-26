---
phase: 24-frontend-plex-cleanup
plan: 01
status: complete
started: 2026-04-26T00:00:00Z
finished: 2026-04-26T00:00:00Z
---

## What Was Built

Added a GET /jellyfin/server-info endpoint that exposes baseUrl and webUrl without credentials, and extended server_info() with a webUrl field in both code paths. Renamed all .plex-yellow CSS class references to .accent-text and .plex-open-btn to .cta-btn across the entire template to remove Plex-branded naming.

## Key Decisions

- The /jellyfin/server-info endpoint returns 200 even on error (empty strings) to avoid breaking frontend logic
- Only baseUrl (machineIdentifier) and webUrl are exposed — no sensitive server details

## Files Changed

- `jellyswipe/__init__.py` — Added GET /jellyfin/server-info route after jellyfin-login route
- `jellyswipe/jellyfin_library.py` — Added "webUrl": self._base to both return dicts in server_info()
- `jellyswipe/templates/index.html` — Renamed .plex-yellow to .accent-text (CSS def + 8 HTML usages), .plex-open-btn to .cta-btn (CSS def + 1 JS usage)

## Verification

```
$ grep -c "plex-yellow\|plex-open-btn" jellyswipe/templates/index.html
0
$ grep -n "jellyfin/server-info" jellyswipe/__init__.py
275:@app.route("/jellyfin/server-info", methods=["GET"])
$ grep -n "webUrl" jellyswipe/jellyfin_library.py
352:                "webUrl": self._base,
361:                "webUrl": self._base,
$ python -c "import ast; ast.parse(open('jellyswipe/__init__.py').read())"
SYNTAX OK
```

## Self-Check: PASSED

All acceptance criteria met.
