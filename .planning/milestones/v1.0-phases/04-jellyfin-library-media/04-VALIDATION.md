---
phase: 4
slug: jellyfin-library-media
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-24
---

# Phase 4 — Validation Strategy

> Evidence and closure notes: [04-VERIFICATION.md](./04-VERIFICATION.md). Plex baseline: [02-VERIFICATION.md](../02-media-provider-abstraction/02-VERIFICATION.md).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | none — documentation + compile + `rg` + Flask `test_client()` where cited in verification |
| **Config file** | none |
| **Quick run command** | `python -m py_compile app.py media_provider/jellyfin_library.py` |
| **Full suite command** | Quick + `rg "JLIB-0" .planning/phases/04-jellyfin-library-media/04-VERIFICATION.md` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After edits to library or routes:** `python -m py_compile app.py media_provider/jellyfin_library.py`
- **After verification doc updates:** `rg "JLIB-0" .planning/phases/04-jellyfin-library-media/04-VERIFICATION.md`
- **Before marking JLIB rows PASS:** Operator re-runs ARC-02 checklist in `04-VERIFICATION.md` against live Jellyfin (no tokens in logs).

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-doc-01 | — | — | JLIB-01 | T-08-01 | Card keys / `id` mapping | grep + compile | `rg "JLIB-01" .planning/phases/04-jellyfin-library-media/04-VERIFICATION.md` && `python -m py_compile app.py media_provider/jellyfin_library.py` | ✅ | ✅ green |
| 04-doc-02 | — | — | JLIB-02 | T-08-01 | Ordering / empty genres path | grep | `rg "JLIB-02" .planning/phases/04-jellyfin-library-media/04-VERIFICATION.md` | ✅ | ✅ green |
| 04-doc-03 | — | — | JLIB-03 | T-08-01 | `/proxy` allowlist | grep | `rg "JLIB-03" .planning/phases/04-jellyfin-library-media/04-VERIFICATION.md` | ✅ | ✅ green |
| 04-doc-04 | — | — | JLIB-04 | T-08-01 | TMDB resolution errors | grep | `rg "JLIB-04" .planning/phases/04-jellyfin-library-media/04-VERIFICATION.md` | ✅ | ✅ green |
| 04-doc-05 | — | — | JLIB-05 | T-08-01 | server-info JSON | grep | `rg "JLIB-05" .planning/phases/04-jellyfin-library-media/04-VERIFICATION.md` | ✅ | ✅ green |

---

## Wave 0 Requirements

- [x] **N/A — pytest not introduced in Phase 8** — Same rationale as Phases 3 and 7; durable gates are compile, `rg` on verification anchors, and manual Jellyfin deck/proxy rows documented in `04-VERIFICATION.md`.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Full deck + images | JLIB-01 — JLIB-03 | Needs live Jellyfin with movies library | Run Flask with valid `JELLYFIN_*`, create room, hit `/movies`, `/genres`, `/proxy?path=jellyfin/{itemId}/Primary`; record HTTP status and JSON keys (no tokens). |
| Trailer / cast happy path | JLIB-04 | Needs resolvable item ids | Use `movie_id` from deck JSON `id`; `GET /get-trailer/<id>` and `GET /cast/<id>` per `08-E2E.md`. |

---

## Validation Sign-Off

- [x] All tasks have documented verify steps or grep checks
- [x] No verification markdown contains raw secrets
- [x] `nyquist_compliant: true` and `wave_0_complete: true` set in frontmatter when file completes

**Approval:** approved 2026-04-24
