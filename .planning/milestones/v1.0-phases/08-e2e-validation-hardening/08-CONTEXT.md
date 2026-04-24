# Phase 8: E2E and validation hardening - Context

**Gathered:** 2026-04-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Close **milestone-level** confidence gaps: **doc-first E2E evidence** for Jellyfin flows (login → room → swipe → trailer/cast), bring **`01-VALIDATION.md`–`05-VALIDATION.md`** to roadmap-complete shape (not draft/missing), and prepare **re-audit inputs** so `/gsd-audit-milestone` can run against fresh artifacts. This phase does **not** add new product capabilities; it hardens evidence, validation coverage, and audit readiness.

</domain>

<decisions>
## Implementation Decisions

### E2E evidence mechanism
- **D-01:** **Doc-first** E2E: reproducible markdown plus commands (`curl`, Flask `test_client`, small `python -c` snippets), consistent with Phases 6–7 closure style.
- **D-02:** **Manual / operator-run** evidence; **no requirement** to add CI E2E or browser automation in this phase (existing CI, e.g. Docker image build, unchanged unless a plan explicitly justifies more).
- **D-03:** Primary milestone flow narrative lives in **`08-E2E.md`** (name may vary slightly but phase-8-owned), with **links** into `07-VERIFICATION.md` and phase-native `03` / `04` / `05` verification files—not a bulk rewrite of `07-VERIFICATION.md` as the E2E container.
- **D-04:** Runs use **operator-provided** Jellyfin (and Plex only if needed for a documented gap); **no secrets** in artifacts; follow Phase 7 **redaction** discipline.

### Flow scope: Jellyfin vs Plex
- **D-05:** **Jellyfin** gets the **full** hands-on E2E narrative required by roadmap success criteria. **Plex** parity is **referenced** via `02-VERIFICATION.md` and Phase 6 artifacts unless execution discovers a **new gap** that forces extra Plex steps.
- **D-06:** Phase 8 **does not** commit to flipping **ARC-02** to Done by itself; it **documents** Jellyfin milestone flows and **links** existing Plex evidence; any ARC-02 status change still follows **evidence-linked** updates in `REQUIREMENTS.md`.
- **D-07:** If E2E results **conflict** with prior verification, treat as **bug or documentation fix** with a tracked follow-up; E2E records **observed** behavior.
- **D-08:** E2E includes **two browser identities** (or sessions) where relevant for **JUSR-01**-style isolation.

### Nyquist / VALIDATION.md strategy
- **D-09:** **`01-VALIDATION.md` … `05-VALIDATION.md`** remain the **authoritative** validation artifacts; Phase 8 **edits them in place** until roadmap completeness (no draft/missing for the Phase 8 bar).
- **D-10:** **Completeness** means each checklist area is **done** or **N/A with rationale**—not only rows cherry-picked from the milestone audit.
- **D-11:** **Nyquist** / `gsd-validate-phase` (or similar) output should **feed** those per-phase files as the **durable** record, not live only in chat logs.
- **D-12:** **`08-E2E.md` cross-links** into the relevant **`NN-VALIDATION.md`** sections for each flow step so auditors have one navigation path.

### Milestone re-audit deliverable
- **D-13:** **Update** `.planning/v1.0-MILESTONE-AUDIT.md` **in place** with current gaps, status, and pointers to `08-E2E.md`, refreshed `NN-VALIDATION.md`, and `REQUIREMENTS.md` traceability.
- **D-14:** “Ready for `/gsd-audit-milestone`” means **all Phase 8 roadmap success criteria** are met **and** `v1.0-MILESTONE-AUDIT.md` has **no blocking** open items without an explicit owner, deferral, or pointer.
- **D-15:** **New gaps** discovered during execution go to **Deferred / backlog** (e.g. ROADMAP `999.x`); do **not** silently widen Phase 8 scope.
- **D-16:** Audit narrative targets **future maintainers**: concise, **link-heavy**, assumes repository context.

### Claude's Discretion
- Exact filenames (`08-E2E.md` vs `08-VERIFICATION.md` for the flow doc) if one umbrella file stays shorter.
- Wording and table layout inside `NN-VALIDATION.md` and `v1.0-MILESTONE-AUDIT.md` updates.
- How much interpretive prose sits in `08-E2E.md` versus pure step lists, as long as reproducibility and redaction rules hold.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone and requirements
- `.planning/ROADMAP.md` — Phase 8 goal, success criteria, requirement IDs.
- `.planning/REQUIREMENTS.md` — Traceability table; updates only with linked evidence (Phases 6–7 discipline).
- `.planning/v1.0-MILESTONE-AUDIT.md` — Re-audit source; Phase 8 **updates this file in place** per D-13.

### Product and constraints
- `.planning/PROJECT.md` — Either/or provider, security, compatibility.

### Prior closure pattern (must align)
- `.planning/phases/06-verification-closure-foundation-abstraction/06-CONTEXT.md` — Phase 6 verification + index pattern.
- `.planning/phases/06-verification-closure-foundation-abstraction/06-VERIFICATION.md` — Index shape reference.
- `.planning/phases/07-verification-closure-jellyfin-parity/07-CONTEXT.md` — Phase 7 evidence bar, redaction, E2E wiring subsection expectations.
- `.planning/phases/07-verification-closure-jellyfin-parity/07-VERIFICATION.md` — Jellyfin closure index; link target from `08-E2E.md`.

### Per-phase validation (authoritative for Nyquist completion)
- `.planning/phases/01-configuration-startup/01-VALIDATION.md`
- `.planning/phases/02-media-provider-abstraction/02-VALIDATION.md`
- `.planning/phases/03-jellyfin-authentication-http-client/03-VALIDATION.md`
- `.planning/phases/04-jellyfin-library-media/04-VALIDATION.md`
- `.planning/phases/05-user-parity-packaging/05-VALIDATION.md`

### Plex parity evidence (cited from Jellyfin-forward E2E)
- `.planning/phases/02-media-provider-abstraction/02-VERIFICATION.md` — ARC-02 / Plex-side checklist and notes.

### Runtime / code touchpoints (for E2E steps and validation hooks)
- `app.py` — Routes, provider branches, proxy, TMDB, user headers.
- `media_provider/jellyfin_library.py` — Jellyfin provider behavior.
- `media_provider/factory.py` — Provider selection.
- `templates/index.html` — Client auth/header behavior if referenced in flows.

### Codebase intelligence
- `.planning/codebase/ARCHITECTURE.md` — Monolith and data flow.
- `.planning/codebase/TESTING.md` — No pytest tree today; suggested patterns for any scripted checks.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable assets
- **Phase 6–7 verification files** — Templates for pass/fail tables, closure notes, and cross-phase narrative.
- **`app.py` + `media_provider/*`** — Surfaces to exercise in doc-first E2E and validation updates.

### Established patterns
- **Evidence in markdown**, reproducible commands, **no secrets** in planning artifacts.
- **No automated test harness** in-repo today per `.planning/codebase/TESTING.md`; Phase 8 does **not** mandate introducing pytest/Playwright as a gate unless a plan explicitly chooses otherwise.

### Integration points
- **`08-E2E.md`** links outward to **`07-VERIFICATION.md`**, **`03`/`04`/`05` verification**, and **`01–05` validation** files.
- **`REQUIREMENTS.md`** and **`v1.0-MILESTONE-AUDIT.md`** consume completed validation and E2E outputs.

</code_context>

<specifics>
## Specific Ideas

- Operator **multi-session** Jellyfin checks should mirror the **dual identity** spirit used in Jellyfin user-parity verification.
- Quick capture: local dev hit **`OSError: [Errno 24] Too many open files`** under Werkzeug — see `.planning/notes/2026-04-24-testing-local-too-many-open-files.md` if follow-up hardening is scheduled outside Phase 8 scope.

</specifics>

<deferred>
## Deferred Ideas

- **Resource exhaustion / dev server robustness** — Handling `errno 24` and degraded image serving after FD exhaustion is **not** in Phase 8 scope; captured in project note above for a future fix or ops doc.

</deferred>

---

*Phase: 08-e2e-validation-hardening*
*Context gathered: 2026-04-24*
