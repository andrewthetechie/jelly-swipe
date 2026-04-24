---
phase: 05
slug: user-parity-packaging
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-23
---

# Phase 05 — Validation Strategy

> Closure evidence: [05-VERIFICATION.md](./05-VERIFICATION.md).

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | none — `py_compile`, route smoke, `docker build` |
| **Config file** | none |
| **Quick run command** | `python -m py_compile app.py media_provider/*.py` |
| **Full suite command** | `docker build .` |
| **Estimated runtime** | ~120s (full includes image build) |

## Sampling Rate

- After each task: run py_compile and route smoke.
- After each plan: run jellyfin dual-user manual checks where applicable.
- Before verify: run `docker build .` when packaging surface changes.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | JUSR-* | T-08-01 | Doc + code | grep | `rg "05-01-01|JUSR-" .planning/phases/05-user-parity-packaging/05-VERIFICATION.md` | ✅ | ✅ green |
| 05-01-02 | 01 | 1 | JUSR-* | T-08-01 | Doc + code | grep | `rg "05-01-02" .planning/phases/05-user-parity-packaging/05-VERIFICATION.md` | ✅ | ✅ green |
| 05-02-01 | 02 | 1 | JUSR-* | T-08-01 | Doc + code | grep | `rg "05-02-01" .planning/phases/05-user-parity-packaging/05-VERIFICATION.md` | ✅ | ✅ green |
| 05-02-02 | 02 | 1 | JUSR-* | T-08-01 | Packaging | shell | `docker build .` (manual gate; record outcome in verification) | ✅ | ✅ green |

## Wave 0 Requirements

- [x] **N/A — pytest not introduced for Phase 5 closure bar** — Gates are `python -m py_compile app.py media_provider/*.py`, `rg` on `05-VERIFICATION.md`, and `docker build .` as full packaging check per JUSR-04 spirit.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Instructions |
|----------|-------------|------------|-------------|
| Dual user partition | JUSR-01 | Browser/session state | Login as two users, create/join same room, verify `matches`/`history` separated by provider user id |
| List add parity | JUSR-02 | Needs real Jellyfin user token | Open shortlist card, add to watchlist/favorites, confirm in Jellyfin UI |
| Header contract | JUSR-03 | Frontend + server integration | Inspect network requests and server behavior in jellyfin mode |
| Packaging | JUSR-04 | Build environment | `pip install -r requirements.txt` and `docker build .` pass |

## Validation Sign-Off

- [x] All tasks have documented verify steps or grep / build gates
- [x] Per-task map references executed plan task IDs and `05-VERIFICATION.md`
- [x] No watch-mode flags
- [x] `nyquist_compliant: true` and `wave_0_complete: true` set in frontmatter

**Approval:** approved 2026-04-24
