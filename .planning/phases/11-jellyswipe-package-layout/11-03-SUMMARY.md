---
phase: 11-jellyswipe-package-layout
plan: 03
subsystem: package-layout
tags: [flask, hatchling, package-data, static-assets, templates]

# Dependency graph
requires:
  - phase: 11-jellyswipe-package-layout-plan-02
    provides: jellyswipe/__init__.py with Flask app, jellyswipe/ package structure
provides:
  - jellyswipe/templates/ directory with index.html
  - jellyswipe/static/ directory with PWA assets (icons, manifest, images)
  - pyproject.toml configured to package templates and static as shared data
  - Flask app configured to find templates and static from jellyswipe package
affects: [phase-12]

# Tech tracking
tech-stack:
  added: []
  patterns: [package data inclusion with hatchling, explicit Flask folder configuration]

key-files:
  created: [jellyswipe/templates/index.html, jellyswipe/static/*]
  modified: [pyproject.toml, jellyswipe/__init__.py]

key-decisions:
  - "Per D-12, templates/ and static/ moved under jellyswipe/ package directory"
  - "Per D-13, pyproject.toml configured with hatchling shared-data for templates and static"
  - "Per D-14, Flask app configured with explicit template_folder and static_folder pointing to jellyswipe/ subdirectories"
  - "Per D-15, data/ remains at repo root (not moved to package)"

patterns-established:
  - "Pattern 7: Package templates and static assets are included in build via hatchling shared-data"
  - "Pattern 8: Flask explicitly configured to find templates/static from package subdirectory with _APP_ROOT"

requirements-completed: [PKG-01]

# Metrics
duration: 3.5min
completed: 2026-04-25
---

# Phase 11 Plan 3: Templates and Static Assets Package Data Summary

**templates/ and static/ moved under jellyswipe/ package with pyproject.toml hatchling configuration and Flask path updates**

## Performance

- **Duration:** 3.5 min
- **Started:** 2026-04-25T01:41:00Z
- **Completed:** 2026-04-25T01:44:31Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Moved templates/ and static/ directories under jellyswipe/ package using git mv to preserve history
- Configured pyproject.toml with [build-system] and [tool.hatch.build.targets.wheel.shared-data] sections
- Updated Flask instantiation in jellyswipe/__init__.py with explicit template_folder and static_folder parameters
- Verified Flask correctly finds templates and static from new locations
- Verified template rendering and static file access work correctly
- Confirmed data/ remains at repo root as required per D-15

## Task Commits

Each task was committed atomically:

1. **Task 1: Move templates/ and static/ under jellyswipe/** - `a9faf63` (refactor)
2. **Task 2: Update pyproject.toml to include templates and static in package data** - `80dfebd` (feat)
3. **Task 3: Configure Flask to find templates and static from jellyswipe package** - `f03ed91` (feat)

**Plan metadata:** [pending final commit]

## Files Created/Modified

- `jellyswipe/templates/index.html` - Main UI template (moved from templates/)
- `jellyswipe/static/icon-192.png` - PWA icon 192x192 (moved from static/)
- `jellyswipe/static/icon-512.png` - PWA icon 512x512 (moved from static/)
- `jellyswipe/static/logo.png` - App logo (moved from static/)
- `jellyswipe/static/main.png` - Main app image (moved from static/)
- `jellyswipe/static/brick.png` - Brick image (moved from static/)
- `jellyswipe/static/sad.png` - Sad face image (moved from static/)
- `jellyswipe/static/manifest.json` - PWA manifest (moved from static/)
- `pyproject.toml` - Added [build-system] and [tool.hatch.build.targets.wheel.shared-data] sections
- `jellyswipe/__init__.py` - Updated Flask instantiation with explicit template_folder and static_folder parameters

## Decisions Made

- Followed D-12: Moved templates/ and static/ under jellyswipe/ package directory using git mv to preserve history
- Followed D-13: Added hatchling build-system configuration with shared-data for templates and static directories
- Followed D-14: Updated Flask app instantiation with explicit template_folder and static_folder pointing to _APP_ROOT subdirectories
- Followed D-15: Kept data/ at repo root (not moved to package)
- Used hatchling shared-data approach (not include pattern) as it's cleaner for package data

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Git lock file conflict during git mv (resolved by removing .git/index.lock)
- Flask initially looking for templates at old location (resolved by adding explicit template_folder and static_folder parameters)

## Verification Results

✓ jellyswipe/templates/ exists with index.html
✓ jellyswipe/static/ exists with all assets (icons, manifest, images)
✓ templates/ and static/ at repo root are removed
✓ pyproject.toml includes [tool.hatch.build.targets.wheel.shared-data] configuration
✓ Flask app.template_folder points to jellyswipe/templates
✓ Flask app.static_folder points to jellyswipe/static
✓ Template rendering works (tested with render_template)
✓ Static files accessible (verified icon-192.png, manifest.json, logo.png exist)
✓ data/ remains at repo root

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Package layout complete with templates and static assets under jellyswipe/
- pyproject.toml configured to include package data in builds
- Flask app correctly configured to find assets from package
- Ready for Phase 12: Dockerfile and documentation updates to use uv and jellyswipe package

## Threat Surface Scan

No new security-relevant surface introduced. Changes are directory reorganization and build configuration only:
- Template path traversal threat (T-11-06) accepted - existing security model unchanged
- Static file path traversal threat (T-11-07) accepted - existing security model unchanged
- Flask static and template serving use same Flask security patterns as before
- No new network endpoints or auth paths introduced

## Known Stubs

None - no placeholder code or stubs found.

## Self-Check: PASSED

All verification checks passed:
- ✓ jellyswipe/templates/index.html exists
- ✓ jellyswipe/static/ directory exists with 7 files
- ✓ templates/ at root removed
- ✓ static/ at root removed
- ✓ data/ at root exists (per D-15)
- ✓ pyproject.toml includes [build-system] with hatchling
- ✓ pyproject.toml includes [tool.hatch.build.targets.wheel.shared-data]
- ✓ Flask app.template_folder points to jellyswipe/templates
- ✓ Flask app.static_folder points to jellyswipe/static
- ✓ Template rendering test passes
- ✓ SUMMARY.md exists
- ✓ Commit a9faf63 (Task 1) exists
- ✓ Commit 80dfebd (Task 2) exists
- ✓ Commit f03ed91 (Task 3) exists

---
*Phase: 11-jellyswipe-package-layout*
*Completed: 2026-04-25*
