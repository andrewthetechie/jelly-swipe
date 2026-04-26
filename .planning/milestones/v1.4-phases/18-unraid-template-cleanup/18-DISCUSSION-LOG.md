# Phase 18: Unraid Template Cleanup - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the analysis.

**Date:** 2026-04-25
**Phase:** 18-unraid-template-cleanup
**Mode:** discuss
**Areas discussed:** Jellyfin Authentication Method, Placeholder values for non-masked fields, CI lint implementation

## Discussion Summary

### Area 1: Jellyfin Authentication Method

**Question:** How should the Unraid template handle Jellyfin authentication?

**Options presented:**
- Both options — Include all three fields (JELLYFIN_API_KEY, JELLYFIN_USERNAME, JELLYFIN_PASSWORD) and let user choose (recommended — matches app flexibility)
- API key only — Simpler — only JELLYFIN_API_KEY and JELLYFIN_URL (matches best practice for server admins)
- Username/password only — Easiest for users — JELLYFIN_USERNAME, JELLYFIN_PASSWORD, JELLYFIN_URL

**User selected:** API key only

**Decision captured:** D-01 — Template will use Jellyfin authentication method: API key only

### Area 2: Placeholder values for non-masked fields

**Question:** Should JELLYFIN_URL have a placeholder value or be blank?

**Options presented:**
- Blank — Leave JELLYFIN_URL empty (consistent with masked fields, cleaner)
- Example format — Show 'http://jellyfin:8096' as hint (helps users know expected format)

**User selected:** Blank

**Decision captured:** D-02 — All fields will be blank by default

### Area 3: CI lint implementation approach

**Question 1:** How should the Unraid template lint be implemented in CI?

**Options presented:**
- Add to test.yml — Add lint step to existing test workflow (runs on push/PR, already has Python environment)
- Separate workflow — Create new unraid-template-lint.yml (isolated, can run independently)

**User selected:** Separate workflow

**Question 2:** What should happen if the Unraid template lint fails in CI?

**Options presented:**
- Block PR — Fail the workflow and prevent merge (strict — ensures template always matches app)
- Warn only — Show warning but allow PR to continue (more flexible for fixes)

**User selected:** Block PR

**Decision captured:** D-03 — Create separate GitHub Actions workflow with block-on-fail behavior

## Codebase Analysis Performed

**Files scanned:**
- `unraid_template/jelly-swipe.html` — Identified Plex variables (PLEX_URL, PLEX_TOKEN) and fake placeholders
- `jellyswipe/__init__.py` — Extracted recognized environment variables
- `jellyswipe/jellyfin_library.py` — Confirmed authentication methods supported

**Key findings:**
- Application supports two auth methods: API key (JELLYFIN_API_KEY) or username/password (JELLYFIN_USERNAME + JELLYFIN_PASSWORD)
- Recognized env vars: JELLYFIN_URL, JELLYFIN_API_KEY, JELLYFIN_USERNAME, JELLYFIN_PASSWORD, TMDB_API_KEY, FLASK_SECRET, DB_PATH, JELLYFIN_DEVICE_ID
- Template uses both legacy `<Variable>` and modern `<Config>` sections
- Fake placeholders exist in both masked and non-masked fields

## No Corrections or Scope Creep

All discussion remained within phase boundaries. No deferred ideas were generated.

---

*Discussion log recorded: 2026-04-25*
