---
phase: 09-ui-improvements-the-login-for-jellyfin-username-password-is-
plan: "02"
subsystem: ui-css
tags: [posters, object-fit, pwa]

requires: []
provides:
  - Full-width poster artwork visible on deck, mini-posters, and match popup
affects: [templates-index, data-index-pwa]

tech-stack:
  added: []
  patterns: [letterboxing with #000 backing on .card-front / .mini-front]

key-files:
  created: []
  modified:
    - templates/index.html
    - data/index.html

key-decisions:
  - "object-fit: contain on .movie-card img, .mini-front img, .match-poster-preview; outer card geometry unchanged"

patterns-established:
  - "Parallel edits to templates and data/index.html for poster CSS"

requirements-completed: []

duration: 15min
completed: 2026-04-24
---

# Phase 09 plan 02 summary

**Poster containment:** Replaced `object-fit: cover` with `contain` on main swipe images, mini-poster fronts, and match popup preview. Added `#000` background on `.card-front` and `.mini-front` so letterboxing matches trailer chrome.

## Verification

- `grep -n "object-fit: contain"` counts ≥3 in each HTML file; `.movie-card img` / `.mini-front img` lines no longer use `cover` for those poster surfaces.

## Self-Check: PASSED
