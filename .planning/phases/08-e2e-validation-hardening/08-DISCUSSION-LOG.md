# Phase 8: E2E and validation hardening - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `08-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-04-24
**Phase:** 8-e2e-validation-hardening
**Areas discussed:** E2E evidence mechanism, Flow scope: Jellyfin vs Plex, Nyquist / VALIDATION.md strategy, Milestone re-audit deliverable

---

## E2E evidence mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| 1a | Doc-first markdown + curl / test_client / python -c | ✓ |
| 1b | In-repo browser automation (e.g. Playwright) as gate | |
| 1c | Hybrid: doc now, automation backlog | |

| Option | Description | Selected |
|--------|-------------|----------|
| 2a | Manual/operator evidence; CI unchanged | ✓ |
| 2b | Add CI for new automated checks | |
| 2c | CI for non-browser only | |

| Option | Description | Selected |
|--------|-------------|----------|
| 3a | New `08-E2E.md` (phase-owned) linking 07 + 03/04/05 | ✓ |
| 3b | Extend `07-VERIFICATION.md` as E2E container | |
| 3c | Scattered updates only in 03/04/05 | |

| Option | Description | Selected |
|--------|-------------|----------|
| 4a | Operator Jellyfin + Phase 7 redaction rules | ✓ |
| 4b | docker-compose fixture Jellyfin | |
| 4c | Claude discretion | |

**User's choice:** `defaults` (all recommended / first options)
**Notes:** Aligns with repo having no pytest harness and Phases 6–7 closure style.

---

## Flow scope: Jellyfin vs Plex

| Option | Description | Selected |
|--------|-------------|----------|
| 1a | Jellyfin full E2E; Plex via 02-VERIFICATION / Phase 6 unless gap | ✓ |
| 1b | Jellyfin + Plex full E2E in Phase 8 | |
| 1c | Jellyfin full + short Plex smoke in 08-E2E | |

| Option | Description | Selected |
|--------|-------------|----------|
| 2a | No solo promise to close ARC-02; link evidence | ✓ |
| 2b | Must drive ARC-02 to Done in Phase 8 | |
| 2c | Planner discretion | |

| Option | Description | Selected |
|--------|-------------|----------|
| 3a | Conflict → bug or doc fix follow-up | ✓ |
| 3b | Doc-only reconciliation | |

| Option | Description | Selected |
|--------|-------------|----------|
| 4a | Two browser identities where JUSR-01 relevant | ✓ |
| 4b | Single session only | |

**User's choice:** `defaults`
**Notes:** Jellyfin-forward milestone narrative; ARC-02 remains evidence-governed.

---

## Nyquist / VALIDATION.md strategy

| Option | Description | Selected |
|--------|-------------|----------|
| 1a | 01–05 VALIDATION in place as source of truth | ✓ |
| 1b | Consolidated 08 replaces depth in 01–05 | |
| 1c | Hybrid: 08 index + depth in 01–05 | |

| Option | Description | Selected |
|--------|-------------|----------|
| 2a | Roadmap completeness bar (done / N/A + rationale) | ✓ |
| 2b | Audit-driven only | |
| 2c | Planner discretion | |

| Option | Description | Selected |
|--------|-------------|----------|
| 3a | Nyquist feeds durable NN-VALIDATION.md | ✓ |
| 3b | Ephemeral Nyquist | |

| Option | Description | Selected |
|--------|-------------|----------|
| 4a | 08-E2E links into NN-VALIDATION sections | ✓ |
| 4b | E2E self-contained | |

**User's choice:** `defaults`

---

## Milestone re-audit deliverable

| Option | Description | Selected |
|--------|-------------|----------|
| 1a | Update `v1.0-MILESTONE-AUDIT.md` in place | ✓ |
| 1b | New packet only under phase 8 | |
| 1c | REQUIREMENTS only | |

| Option | Description | Selected |
|--------|-------------|----------|
| 2a | Phase 8 success bullets + audit doc no blocking orphans | ✓ |
| 2b | Phase 8 bullets only | |
| 2c | Planner discretion at end | |

| Option | Description | Selected |
|--------|-------------|----------|
| 3a | New gaps → deferred/backlog; no silent scope creep | ✓ |
| 3b | Absorb small gaps in Phase 8 | |
| 3c | Stop phase until each gap has own phase | |

| Option | Description | Selected |
|--------|-------------|----------|
| 4a | Maintainer audience; concise, link-heavy | ✓ |
| 4b | External reviewer prose + glossary | |

**User's choice:** `defaults`

---

## Claude's Discretion

- Filenames and table cosmetics inside validation and audit markdown.
- Balance of prose vs raw command logs in `08-E2E.md` within D-01/D-04 constraints.

## Deferred Ideas

- Errno 24 / too many open files under local Werkzeug — see `.planning/notes/2026-04-24-testing-local-too-many-open-files.md`; out of Phase 8 product scope, noted for follow-up.
