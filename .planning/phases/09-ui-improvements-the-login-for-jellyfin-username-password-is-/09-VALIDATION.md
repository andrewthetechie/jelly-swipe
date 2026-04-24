---
phase: 09
slug: ui-improvements-the-login-for-jellyfin-username-password-is
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-24
---

# Phase 9 — Validation strategy

> Feedback sampling for Jellyfin delegate auth and poster CSS. No `pytest` tree in repo yet — Wave 0 optional.

---

## Test infrastructure

| Property | Value |
|----------|-------|
| **Framework** | none — manual + `python -c` / Flask `test_client` snippets |
| **Config file** | none |
| **Quick run command** | `python -c "from app import app; ..."` (per plan SUMMARY) |
| **Full suite command** | same as quick until tests land |
| **Estimated runtime** | &lt; 30 seconds |

---

## Sampling rate

- **After every task commit:** Quick grep checks from plan acceptance criteria.
- **After every plan wave:** Re-run delegate `test_client` snippet + CSS grep pair.
- **Before `/gsd-verify-work`:** Full manual UAT row in SUMMARY.

---

## Per-task verification map

| Task ID | Plan | Wave | Requirement | Threat ref | Secure behavior | Test type | Automated command | File exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 09-01-01 | 01 | 1 | Phase goal (delegate) | T-09-01 | No API key in HTTP JSON | manual+snippet | `grep` per acceptance | ⬜ W0 | ⬜ pending |
| 09-01-02 | 01 | 1 | Phase goal (delegate) | T-09-02 | Session-only token resolution | manual+snippet | `python -c` | ⬜ W0 | ⬜ pending |
| 09-02-01 | 02 | 2 | Phase goal (posters) | — | N/A | grep | `rg object-fit: contain` both HTML | ⬜ W0 | ⬜ pending |

---

## Wave 0 requirements

- [ ] Optional: `tests/test_jellyfin_delegate.py` with `test_client` — defer if time-boxed; document in SUMMARY if skipped.

*If none: manual operator checks cover phase requirements.*

---

## Manual-only verifications

| Behavior | Requirement | Why manual | Test instructions |
|----------|-------------|------------|---------------------|
| Wide poster not cropped | Phase 9 poster goal | Visual | Load deck with wide artwork; confirm sides visible vs baseline screenshot |
| Browser prompts gone | Delegate UX | UX | Clear site data; reload; confirm no `prompt()` for Jellyfin on cold load |

---

## Validation sign-off

- [ ] All tasks have grep- or snippet-verifiable acceptance
- [ ] Sampling continuity documented in SUMMARY
- [ ] No watch-mode flags
- [ ] `nyquist_compliant: true` set when operator approves

**Approval:** pending
