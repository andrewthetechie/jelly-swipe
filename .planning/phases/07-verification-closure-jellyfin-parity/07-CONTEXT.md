# Phase 7: Verification closure: Jellyfin parity - Context

**Gathered:** 2026-04-24  
**Status:** Ready for planning

<domain>
## Phase Boundary

Create durable verification artifacts for Phases 3–5 covering Jellyfin **auth**, **library/media parity**, and **user-scope parity**. Each **JAUTH-01–03**, **JLIB-01–05**, and **JUSR-01–04** requirement maps to concrete pass/fail evidence. Cross-phase wiring (auth → library → user flows) is validated and documented. **`.planning/REQUIREMENTS.md`** traceability rows for **J\*** (and any **ARC-02** updates made under the agreed rules) reflect post-verification status.

This phase closes verification and documentation gaps. It does not add new product capabilities.

</domain>

<decisions>
## Implementation Decisions

### Verification file layout
- **D-01:** Mirror Phase 6: author **`03-VERIFICATION.md`**, **`04-VERIFICATION.md`**, and **`05-VERIFICATION.md`** in `.planning/phases/03-jellyfin-authentication-http-client/`, `.planning/phases/04-jellyfin-library-media/`, and `.planning/phases/05-user-parity-packaging/` respectively.
- **D-02:** Add **`07-VERIFICATION.md`** in this phase directory as a concise **index** linking to those phase-native files and summarizing closure status for audits (same pattern as `06-VERIFICATION.md`).

### Evidence bar and runtime validation
- **D-03:** Use the **same evidence bar as Phase 6**: **live runtime** checks for each mapped requirement where meaningful; no closure that is documentation-only when a runtime check is feasible.
- **D-04:** Verification procedures must be **reproducible** (commands/URLs/steps captured in the verification artifacts).

### Secrets and sensitive data in artifacts
- **D-05:** **Never** paste access tokens, API keys, passwords, or full auth headers into verification markdown, logs excerpts, or REQUIREMENTS notes. Describe checks and expected **non-sensitive** outcomes (HTTP status, shape of public fields, error message style without secrets).

### ARC-02 (Jellyfin mode) scope within Phase 7
- **D-06:** Include an explicit **Jellyfin-mode ARC-02** subsection (bounded checklist: deck JSON/genres behavior, `/proxy` Jellyfin paths, trailer/cast chain, server-info, key user-scoped routes) in the verification set, with **cross-reference** to Phase 6 Plex-side `02-VERIFICATION.md` where it helps auditors compare intent. Goal: move **ARC-02** off indeterminate “partial with no Jellyfin story” where evidence supports it.

### Cross-phase wiring narrative
- **D-07:** **`07-VERIFICATION.md`** must contain a **dedicated end-to-end subsection** (operator/server auth → library deck load → user identity headers and user-scoped routes) with pass/fail and pointers into the 03/04/05 verification files—not only cross-links without a single narrative thread.

### Requirements traceability updates
- **D-08:** Update **`.planning/REQUIREMENTS.md`** only when verification artifacts contain **linked evidence** for the row being changed. **No** status flips without a verification anchor (same discipline as Phase 6).
- **D-09:** **J\*** rows are primary. **ARC-02** may be updated in the same pass when **D-06** evidence is recorded; do not mark ARC-02 done on speculation.

### README and operator-facing documentation
- **D-10:** README (and similar operator docs) updates are **in scope** during Phase 7 when **J\*** (or the ARC-02 slice) **explicitly** requires documentation, or when verification **fails** until documentation reflects actual behavior. Prefer minimal, evidence-driven edits.

### Session note
- **D-11:** User selected **all** gray areas for discussion and locked choices **`1a 2a 3a 4a 5a 6a 7a`** (all recommended defaults).

### Claude's Discretion
- Exact table layout, command snippets, and section headings inside each `*-VERIFICATION.md` file.
- How much to duplicate vs link from `07-VERIFICATION.md` as long as the index remains audit-friendly.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone closure and roadmap
- `.planning/v1.0-MILESTONE-AUDIT.md` — Source gaps motivating verification closure work.
- `.planning/ROADMAP.md` — Phase 7 goal, requirement IDs, success criteria.
- `.planning/REQUIREMENTS.md` — **JAUTH-01–03**, **JLIB-01–05**, **JUSR-01–04**, **ARC-02** wording and traceability table.

### Product and constraints
- `.planning/PROJECT.md` — Security (no token logging), either-or provider, compatibility notes.

### Prior verification pattern (must align)
- `.planning/phases/06-verification-closure-foundation-abstraction/06-CONTEXT.md` — Phase 6 closure decisions (native verification files + index, live evidence, traceability rules).
- `.planning/phases/06-verification-closure-foundation-abstraction/06-VERIFICATION.md` — Index shape and snapshot table pattern.
- `.planning/phases/01-configuration-startup/01-VERIFICATION.md` — Example phase-native verification structure.
- `.planning/phases/02-media-provider-abstraction/02-VERIFICATION.md` — ARC-02 checklist and Plex-side evidence (compare for Jellyfin ARC-02 slice).

### Implementation decisions to verify against
- `.planning/phases/03-jellyfin-authentication-http-client/03-CONTEXT.md` — JAUTH decisions.
- `.planning/phases/04-jellyfin-library-media/04-CONTEXT.md` — JLIB decisions.
- `.planning/phases/05-user-parity-packaging/05-CONTEXT.md` — JUSR decisions.

### Runtime / code touchpoints
- `app.py` — Routes, Jellyfin branches, proxy, TMDB, user headers.
- `media_provider/jellyfin_library.py` — Jellyfin provider behavior.
- `media_provider/factory.py` — Provider selection and reset.
- `media_provider/plex_library.py` — Parity reference for ARC-02 comparisons.
- `templates/index.html` — Client headers and Jellyfin auth path if referenced in JUSR checks.

### Codebase intelligence
- `.planning/codebase/ARCHITECTURE.md` — Monolith and data flow.
- `.planning/codebase/INTEGRATIONS.md` — External HTTP and auth patterns.

### External
- Official Jellyfin REST/OpenAPI for the operator’s target server version — for reconciling any ambiguous “expected behavior” during verification.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable assets
- **Phase 6 verification files** — Template for tables, traceability rows, and closure notes (`01-VERIFICATION.md`, `02-VERIFICATION.md`, `06-VERIFICATION.md`).
- **`media_provider/jellyfin_library.py`** — Primary surface for JLIB/JAUTH runtime checks.
- **`app.py`** — Integration point for routes, `MEDIA_PROVIDER` branching, `/proxy`, TMDB helpers, and user-scoped APIs.

### Established patterns
- **Phase-native `NN-VERIFICATION.md`** next to the phase that implemented the behavior; **closure phase index** for navigation.
- **JSON error responses** must not echo secrets — verification should assert that behavior, not introduce new logging.

### Integration points
- Verification evidence in **03/04/05** files feeds **`07-VERIFICATION.md`** and then **`.planning/REQUIREMENTS.md`** traceability.
- Jellyfin **ARC-02** slice should tie Jellyfin-mode behavior to the same route-level concerns documented for Plex in `02-VERIFICATION.md`.

</code_context>

<specifics>
## Specific Ideas

- User aligned with **recommended** options across all four gray areas (`1a`–`7a`): mirror Phase 6 file topology, full live runtime bar, strict no-secrets-in-artifacts rule, include Jellyfin ARC-02 slice, dedicated E2E subsection in the phase 7 index, strict traceability updates, README in scope when requirements or failures demand it.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 07-verification-closure-jellyfin-parity*  
*Context gathered: 2026-04-24*
