---
phase: 18-unraid-template-cleanup
plan: 02
subsystem: infrastructure
tags: github-actions, yaml, python, lint, unraid, validation, ci

# Dependency graph
requires:
  - phase: 17-testing
    provides: pytest framework with GitHub Actions test workflow pattern
  - phase: 18-unraid-template-cleanup
    plan: 01
    provides: Unraid template with Jellyfin variables
provides:
  - CI lint workflow for Unraid template validation
  - Python script to extract and validate template variables
  - Automatic blocking of PRs with unknown environment variables
affects: code-review, deployment, template-maintenance

# Tech tracking
tech-stack:
  added:
    - Python xml.etree.ElementTree for XML parsing
  patterns:
    - GitHub Actions workflow with path-based triggers
    - Python exit code 1 for CI failure propagation
    - Quoted YAML keys to avoid boolean keyword parsing

key-files:
  created:
    - .github/workflows/unraid-template-lint.yml
    - scripts/lint-unraid-template.py
  modified: []

key-decisions:
  - "Config entries with Type=\"Variable\" are the only environment variables in Unraid templates"
  - "Quoted 'on' key in YAML to prevent boolean keyword parsing"

patterns-established:
  - "Pattern 1: Unraid template variables must be a strict subset of recognized app env vars"
  - "Pattern 2: GitHub Actions workflows must quote boolean keywords (on, yes, true) as string keys"

requirements-completed: [CI-01]

# Metrics
duration: 5min
completed: 2026-04-26
---

# Phase 18 Plan 02: Create CI lint workflow to validate Unraid template variables Summary

**GitHub Actions workflow and Python script lint Unraid template to verify environment variables are a strict subset of recognized app env vars, blocking PRs on invalid templates**

## Performance

- **Duration:** 5 min (289 seconds)
- **Started:** 2026-04-26T05:02:23Z
- **Completed:** 2026-04-26T05:07:12Z
- **Tasks:** 1
- **Files created:** 2
- **Commits:** 2

## Accomplishments

- Created Python script `scripts/lint-unraid-template.py` that parses Unraid template XML and extracts variable names
- Script correctly identifies environment variables from both `<Variable>` (legacy) and `<Config Type="Variable">` (modern) sections
- Script compares extracted variables against recognized set of 8 app env vars and fails with exit code 1 on unknown vars
- Created GitHub Actions workflow `.github/workflows/unraid-template-lint.yml` that triggers on push/PR to template file
- Workflow runs lint script and fails the build if validation fails, blocking PR merge
- Successfully validated current Jellyfin template (4 recognized vars: JELLYFIN_URL, JELLYFIN_API_KEY, TMDB_API_KEY, FLASK_SECRET)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create CI lint workflow and Python script for template validation** - `67b0a9b` (feat)
2. **Task 1 Fix: Quote 'on' key in YAML to avoid boolean keyword parsing** - `8d50630` (fix)

**Plan metadata:** `lmn012o` (docs: complete plan)

## Files Created/Modified

- `scripts/lint-unraid-template.py` - Python script that parses Unraid template XML, extracts environment variables from `<Variable>` and `<Config>` sections, validates against recognized app env vars, exits with code 1 on unknown variables
- `.github/workflows/unraid-template-lint.yml` - GitHub Actions workflow that triggers on push/PR to `unraid_template/jelly-swipe.html`, runs Python 3.13, executes lint script

## Decisions Made

- Config entries with `Type="Variable"` are the only environment variables in Unraid templates (others like "Port" and "Path" types are configuration, not env vars)
- Quoted 'on' key in YAML to prevent boolean keyword parsing (YAML treats "on" as boolean true, GitHub Actions requires it as string key)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Config entries filtering required for environment variables**
- **Found during:** Task 1 (Initial script test)
- **Issue:** Script was extracting all Config entries including "WebUI Port" and "AppData Config Path" which are not environment variables (they have Type="Port" and Type="Path")
- **Fix:** Updated script to only extract Config entries where `Type="Variable"` attribute is present
- **Files modified:** `scripts/lint-unraid-template.py`
- **Verification:** Script now correctly identifies only 4 environment variables, validation passes
- **Committed in:** `67b0a9b` (part of Task 1 commit)

**2. [Rule 1 - Bug] YAML boolean keyword 'on' must be quoted**
- **Found during:** Task 1 (YAML validation with Python)
- **Issue:** YAML parser treated unquoted "on:" as boolean "true:" key, making the workflow invalid for GitHub Actions
- **Fix:** Quoted "on:" in workflow YAML to make it a string key
- **Files modified:** `.github/workflows/unraid-template-lint.yml`
- **Verification:** YAML parser now correctly reads workflow structure, GitHub Actions can parse it
- **Committed in:** `8d50630` (separate fix commit)

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both auto-fixes necessary for correctness. The Config type filtering is essential for accurate validation. The YAML quoting fix is required for the workflow to run at all. No scope creep.

## Issues Encountered

- Initial script extracted all Config entries instead of just environment variables - fixed by filtering on `Type="Variable"`
- YAML syntax error with unquoted "on:" key - fixed by quoting the key to prevent boolean interpretation

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- CI lint workflow is active and will validate all future Unraid template changes
- Any PR that adds unknown environment variables to the template will be blocked from merging
- Template is validated against the 8 recognized app env vars: JELLYFIN_URL, JELLYFIN_API_KEY, JELLYFIN_USERNAME, JELLYFIN_PASSWORD, TMDB_API_KEY, FLASK_SECRET, DB_PATH, JELLYFIN_DEVICE_ID

## Self-Check: PASSED

**Created files:**
- ✓ scripts/lint-unraid-template.py
- ✓ .github/workflows/unraid-template-lint.yml
- ✓ .planning/phases/18-unraid-template-cleanup/18-02-SUMMARY.md

**Commits:**
- ✓ 67b0a9b (feat): Create CI lint workflow and Python script for Unraid template validation
- ✓ 8d50630 (fix): Quote 'on' key in YAML to avoid boolean keyword parsing

**Verification:**
- ✓ Script validates correctly against current template (4 recognized vars)
- ✓ YAML parses successfully with quoted 'on' key
- ✓ Workflow structure verified with Python YAML parser

---
*Phase: 18-unraid-template-cleanup*
*Completed: 2026-04-26*
