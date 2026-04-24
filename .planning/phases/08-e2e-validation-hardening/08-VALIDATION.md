---
phase: 8
slug: e2e-validation-hardening
status: draft
nyquist_compliant: false
wave_0_complete: true
created: 2026-04-24
---

# Phase 8 — Validation Strategy

> Documentation, operator E2E, and per-phase `NN-VALIDATION.md` closure for milestone re-audit readiness.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | none — no new pytest harness in Phase 8 baseline |
| **Config file** | none |
| **Quick run command** | `python -m py_compile app.py` (when app touched) |
| **Full suite command** | Quick + `rg -nE "JELLYFIN_API_KEY|PLEX_TOKEN|Authorization:\\s*Bearer" .planning/phases/08-e2e-validation-hardening/08-E2E.md` (expect exit **1**) + `docker build .` before declaring packaging evidence |
| **Estimated runtime** | ~2–5 minutes (dominated by optional `docker build`) |

---

## Sampling Rate

- **After every task commit:** Run quick compile if Python changed; always run secret-negative `rg` on new/changed Phase 8 markdown.
- **After every plan wave:** Re-run full suite command subset relevant to touched artifacts.
- **Before `/gsd-verify-work`:** `08-E2E.md` exists; `01`–`05` `*-VALIDATION.md` present and not `draft` without N/A rationale; `v1.0-MILESTONE-AUDIT.md` references fresh evidence.
- **Max feedback latency:** 180 seconds (excluding full Docker build)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 1 | E2E narrative | T-08-01 | No secrets in `08-E2E.md` | grep + manual | `test -f .planning/phases/08-e2e-validation-hardening/08-E2E.md` | ⬜ | ⬜ pending |
| 08-02-01 | 02 | 2 | Validation closure | T-08-01 | No secrets in new validation files | grep | `test -f .planning/phases/03-jellyfin-authentication-http-client/03-VALIDATION.md` | ⬜ | ⬜ pending |
| 08-02-02 | 02 | 2 | Validation closure | T-08-01 | No secrets | grep | `test -f .planning/phases/04-jellyfin-library-media/04-VALIDATION.md` | ⬜ | ⬜ pending |
| 08-03-01 | 03 | 3 | Re-audit | T-08-02 | No stale “missing VERIFICATION” claims | grep | `rg "08-E2E" .planning/v1.0-MILESTONE-AUDIT.md` | ⬜ | ⬜ pending |

*T-08-01: operator pastes secrets into E2E / validation markdown. T-08-02: audit file left contradictory to on-disk verification.*

---

## Wave 0 Requirements

- **N/A — explicit:** Phase 8 does not install pytest or new CI browsers. Wave 0 marked complete with rationale: evidence lives in markdown + compile/grep/docker per `08-CONTEXT.md` D-02.

---

## Manual-Only Verifications

| Behavior | Source | Why Manual | Test Instructions |
|----------|--------|------------|-------------------|
| Jellyfin login → room → swipe | Roadmap SC #1 | Needs real Jellyfin + browser | Follow `08-E2E.md` operator section; record PASS/FAIL and date |
| Trailer + cast lookup | Roadmap SC #1 | Needs TMDB + Jellyfin metadata | Exercise URLs documented in `08-E2E.md`; cite `04-VERIFICATION.md` rows |
| Dual browser identity isolation (JUSR-01 spirit) | `08-CONTEXT.md` D-08 | Session state | Two profiles or incognito + normal; confirm match rows do not cross |

---

## Validation Sign-Off

- [ ] `08-E2E.md` published with cross-links to `07-VERIFICATION.md` and `03` / `04` / `05` verification files
- [ ] `03-VALIDATION.md` and `04-VALIDATION.md` created; `01` / `02` / `05` validation files finalized (`complete` or documented N/A per checklist area)
- [ ] Secret-negative checks pass on all new/changed operator-facing markdown
- [ ] `v1.0-MILESTONE-AUDIT.md` updated for re-audit
- [ ] `nyquist_compliant: true` set in this file’s frontmatter when above are true

**Approval:** pending
