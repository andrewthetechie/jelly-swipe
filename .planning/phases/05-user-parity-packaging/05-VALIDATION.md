---
phase: 05
slug: user-parity-packaging
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-23
---

# Phase 05 — Validation Strategy

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (future), py_compile/manual now |
| **Config file** | none |
| **Quick run command** | `python -m py_compile app.py media_provider/*.py` |
| **Full suite command** | `docker build .` |
| **Estimated runtime** | ~120s |

## Sampling Rate

- After each task: run py_compile and route smoke.
- After each plan: run jellyfin dual-user manual checks.
- Before verify: run docker build.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Instructions |
|----------|-------------|------------|-------------|
| Dual user partition | JUSR-01 | Browser/session state | Login as two users, create/join same room, verify `matches`/`history` separated by provider user id |
| List add parity | JUSR-02 | Needs real Jellyfin user token | Open shortlist card, add to watchlist/favorites, confirm in Jellyfin UI |
| Header contract | JUSR-03 | Frontend + server integration | Inspect network requests and server behavior in jellyfin mode |
| Packaging | JUSR-04 | Build environment | `pip install -r requirements.txt` and `docker build .` pass |
