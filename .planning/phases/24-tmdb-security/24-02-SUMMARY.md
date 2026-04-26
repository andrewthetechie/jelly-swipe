---
phase: 24-tmdb-security
plan: 02
status: done
commit: f9b319e
---

# Plan 02 Summary: Update docs/config to TMDB_ACCESS_TOKEN

## What Changed

Replaced all `TMDB_API_KEY` references with `TMDB_ACCESS_TOKEN` across 4 files to align documentation and configuration with the new v4 Bearer token authentication.

## Files Modified

| File | Change |
|------|--------|
| `README.md` | Env var table, example env files, TMDB instructions, docker examples, Unraid section — 7 references updated |
| `docker-compose.yml` | Environment variable line updated to `TMDB_ACCESS_TOKEN` |
| `unraid_template/jelly-swipe.html` | Variable name and Config element updated (2 occurrences) |
| `scripts/lint-unraid-template.py` | `RECOGNIZED_VARS` set updated to include `TMDB_ACCESS_TOKEN` |

## Verification Results

- Zero `TMDB_API_KEY` references in all 4 modified files
- `TMDB_ACCESS_TOKEN` occurrences: README.md=7, docker-compose.yml=1, unraid_template=2, lint script=1
- Unraid template lint passes
- README contains "Read Access Token" guidance (4 occurrences)
- TMDB instructions now explain v4 token acquisition with direct link to settings page

## Commit

`f9b319e` — docs: replace TMDB_API_KEY with TMDB_ACCESS_TOKEN across all config and docs
