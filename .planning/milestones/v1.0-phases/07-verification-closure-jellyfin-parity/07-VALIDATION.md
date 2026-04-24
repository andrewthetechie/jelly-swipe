---
phase: 7
slug: verification-closure-jellyfin-parity
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-24
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution (verification documentation phase).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | none — documentation + Flask `test_client` snippets |
| **Config file** | none |
| **Quick run command** | `rg -n "JAUTH-01|JLIB-01|JUSR-01" .planning/phases/0{3,4,5}-*/*-VERIFICATION.md .planning/phases/07-*/*-VERIFICATION.md` |
| **Full suite command** | Same as quick + `rg -nE "JELLYFIN_API_KEY|PLEX_TOKEN|Authorization:" .planning/phases/0{3,4,5}-*/*-VERIFICATION.md .planning/phases/07-*/*-VERIFICATION.md` (expect exit 1) |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick `rg` traceability command for the touched requirement IDs.
- **After every plan wave:** Run full suite `rg` (including secret-pattern negative check).
- **Before `/gsd-verify-work`:** All verification files present and REQUIREMENTS rows link to them.
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 1 | JAUTH-01 — JAUTH-03 | T-07-01 | No secrets in markdown | grep | `rg "JAUTH-0" .planning/phases/03-jellyfin-authentication-http-client/03-VERIFICATION.md` | ✅ | ✅ green |
| 07-02-01 | 02 | 1 | JLIB-01 — JLIB-05 | T-07-01 | No secrets in markdown | grep | `rg "JLIB-0" .planning/phases/04-jellyfin-library-media/04-VERIFICATION.md` | ✅ | ✅ green |
| 07-03-01 | 03 | 1 | JUSR-01 — JUSR-04 | T-07-01 | No secrets in markdown | grep | `rg "JUSR-0" .planning/phases/05-user-parity-packaging/05-VERIFICATION.md` | ✅ | ✅ green |
| 07-04-01 | 04 | 2 | closure + REQ rows | T-07-01 | Traceability only | manual | `rg "07-VERIFICATION" .planning/REQUIREMENTS.md` | ✅ | ✅ green |

---

## Wave 0 Requirements

- [x] Existing repository has no pytest tree — **no** new test framework required for this phase.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|---------------------|
| Full Jellyfin deck + images | JLIB-01 — JLIB-03 | Needs live Jellyfin with movies library | Run Flask with valid `JELLYFIN_*`, create room, hit `/movies`, `/genres`, `/proxy?path=jellyfin/{itemId}/Primary`; record HTTP status and JSON keys (no tokens). |
| End-user favorites | JUSR-02 | Needs user session token from real login | POST `/auth/jellyfin-login` then `/watchlist/add` with `Authorization: MediaBrowser …` carrying user token. |

---

## Validation Sign-Off

- [x] All tasks have documented verify steps or grep checks
- [x] No verification markdown contains raw secrets
- [x] `nyquist_compliant: true` set in frontmatter when phase execution completes

**Approval:** approved 2026-04-24
