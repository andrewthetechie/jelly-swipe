# Phase 7: Verification closure: Jellyfin parity - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.  
> Decisions are captured in `07-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-04-24  
**Phase:** 07 — verification-closure-jellyfin-parity  
**Areas discussed:** Verification file layout, Evidence bar (JAUTH/JLIB/JUSR), Secrets in verification text, ARC-02 (Jellyfin mode) scope, Cross-phase wiring narrative, REQUIREMENTS.md update policy, README / operator docs  

---

## Verification file layout

| Option | Description | Selected |
|--------|-------------|----------|
| **a** | Native `03-` / `04-` / `05-VERIFICATION.md` + `07-VERIFICATION.md` index (mirror Phase 6) | ✓ |
| **b** | Monolithic `07-VERIFICATION.md` only | |
| **c** | Per-phase files only, no phase 7 index | |

**User's choice:** `1a`  
**Notes:** Aligns audit discovery with implementation phase directories; index in phase 7 for navigation.

---

## Evidence bar (JAUTH / JLIB / JUSR)

| Option | Description | Selected |
|--------|-------------|----------|
| **a** | Same as Phase 6 — live runtime for each mapped requirement where meaningful | ✓ |
| **b** | Live for JAUTH + wiring; documented procedure for some JLIB/JUSR | |
| **c** | Documented steps preferred over live for most rows | |

**User's choice:** `2a`  
**Notes:** Strong closure bar; may require a healthy Jellyfin instance for full PASS rows.

---

## Secrets in verification text

| Option | Description | Selected |
|--------|-------------|----------|
| **a** | Never paste tokens/keys/passwords; describe checks and safe outcomes only | ✓ |
| **b** | Allow heavily redacted token prefixes | |

**User's choice:** `3a`  
**Notes:** Matches JAUTH-03 / Phase 3 security decisions.

---

## ARC-02 (Jellyfin mode) in Phase 7

| Option | Description | Selected |
|--------|-------------|----------|
| **a** | Explicit bounded Jellyfin ARC-02 subsection + cross-ref to Phase 6 Plex evidence | ✓ |
| **b** | Phase 7 strictly J\*; defer ARC-02 | |
| **c** | Light paragraph only | |

**User's choice:** `4a`  
**Notes:** Closes the “partial ARC-02 with no Jellyfin story” gap when evidence supports updates.

---

## Cross-phase wiring narrative

| Option | Description | Selected |
|--------|-------------|----------|
| **a** | Dedicated E2E subsection in `07-VERIFICATION.md` | ✓ |
| **b** | Cross-links only between phase files | |
| **c** | Separate `07-E2E-WIRING.md` | |

**User's choice:** `5a`  
**Notes:** Satisfies roadmap success criterion for documented cross-phase validation.

---

## REQUIREMENTS.md updates

| Option | Description | Selected |
|--------|-------------|----------|
| **a** | Same as Phase 6 — traceability changes only with linked verification evidence | ✓ |
| **b** | Update J\* from verification; defer ARC-02 row even if verified | |

**User's choice:** `6a`  
**Notes:** Evidence-linked traceability only; ARC-02 may still be updated when D-06 evidence exists (see `07-CONTEXT.md` D-09).

---

## README / operator documentation

| Option | Description | Selected |
|--------|-------------|----------|
| **a** | In scope when J\* / ARC-02 slice requires docs or verification exposes a doc gap | ✓ |
| **b** | Artifacts only; README in Phase 8 | |
| **c** | README only when a step fails until fixed | |

**User's choice:** `7a`  
**Notes:** Allows proactive README alignment with locked requirements, not only failure-driven edits.

---

## Claude's Discretion

None captured — user chose explicit **a** options throughout.

## Deferred Ideas

None recorded.

---

*Phase: 07-verification-closure-jellyfin-parity*  
*Discussion log: 2026-04-24*
