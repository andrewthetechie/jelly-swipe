---
phase: 29-some-other-changes-to-the-site-html-is-causing-an-error-that
plan: 01
subsystem: ui
tags: [csp, css, fonts, security-headers, flask-static]

# Dependency graph
requires:
  - phase: 28-coverage-enforcement
    provides: Existing index.html with inline styles/scripts
provides:
  - CSP-compliant index.html with external CSS/JS
  - Self-hosted Allura font (woff2)
  - External stylesheet with all UI styles
  - External JavaScript with event delegation pattern
affects: [ui, security, templates]

# Tech tracking
tech-stack:
  added: []
  patterns: [external-css, external-js, event-delegation, css-hover-pseudo-class, self-hosted-fonts, data-attributes]

key-files:
  created:
    - jellyswipe/static/styles.css
    - jellyswipe/static/fonts/Allura-Regular.woff2
    - jellyswipe/static/app.js
  modified:
    - jellyswipe/templates/index.html

key-decisions:
  - "Externalized all CSS to static/styles.css rather than keeping inline <style> block"
  - "Externalized all JS to static/app.js rather than keeping inline <script> block"
  - "Self-hosted Allura font (woff2) from Google Fonts gstatic v23 CDN"
  - "Used event delegation for dynamic elements and addEventListener for static elements"
  - "Used CSS class toggling for solo toggle instead of direct style manipulation"
  - "Used data-genre attributes on genre items instead of inline onclick"

patterns-established:
  - "External CSS file for all styles (no inline style= attributes)"
  - "External JS file with event delegation for dynamic content"
  - "data-* attributes for passing template variables to JS"
  - "Self-hosted fonts in static/fonts/ with @font-face"

requirements-completed: []

# Metrics
duration: 6min
completed: 2026-04-26
---

# Phase 29: Fix CSP Inline Style Errors Summary

**Eliminated all Content-Security-Policy violations by externalizing 34 inline style attributes, ~190 lines of inline CSS, ~320 lines of inline JS, and self-hosting the Allura font**

## Performance

- **Duration:** 6 min
- **Started:** 2026-04-26T22:46:48Z
- **Completed:** 2026-04-26T22:52:49Z
- **Tasks:** 2
- **Files modified:** 4 (2 created, 2 modified)

## Accomplishments
- Eliminated all 34 inline `style=` attributes from index.html (0 remaining)
- Externalized entire `<style>` block (~190 lines) to `static/styles.css`
- Externalized entire `<script>` block (~320 lines) to `static/app.js`
- Self-hosted Allura Regular font (woff2) replacing Google Fonts CDN dependency
- Replaced 3 inline onmouseover/onmouseout hover handlers with CSS `:hover` rules
- Converted all JS template literal inline styles to CSS classes
- Implemented event delegation pattern for dynamic match cards and swipe deck
- All 10 verification checks pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Create external CSS stylesheet and self-host Allura font** - `86787cb` (feat)
2. **Task 2: Refactor index.html for CSP compliance** - `c6d38c0` (feat)

## Files Created/Modified
- `jellyswipe/static/styles.css` - Complete external stylesheet with @font-face, all UI styles, and 34 new CSS classes
- `jellyswipe/static/fonts/Allura-Regular.woff2` - Self-hosted Allura Regular font (26KB woff2)
- `jellyswipe/static/app.js` - All application JavaScript with event delegation and data-attribute patterns
- `jellyswipe/templates/index.html` - Clean HTML with external CSS/JS references, zero inline styles/handlers

## Decisions Made
- Externalized CSS to separate file rather than keeping inline `<style>` block — cleaner and CSP-compliant
- Externalized JS to separate file rather than keeping inline `<script>` block — CSP-compliant and cacheable
- Downloaded Allura font from gstatic v23 URL (v18 URL in plan was outdated) — Rule 3 auto-fix
- Used CSS class toggling (`solo-toggle-active`) for solo toggle instead of direct `element.style.*` manipulation — cleaner pattern
- Used `data-genre` attributes on genre items with event delegation instead of individual onclick handlers

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated font download URL from v18 to v23**
- **Found during:** Task 1 (Font download)
- **Issue:** The plan-specified v18 URL returned HTML instead of woff2 binary (expired/moved resource)
- **Fix:** Queried Google Fonts CSS endpoint to find current v23 URL, downloaded from correct endpoint
- **Files modified:** N/A (download artifact)
- **Verification:** file(1) confirms "Web Open Font Format (Version 2)", 26KB non-zero size
- **Committed in:** 86787cb (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Font URL was outdated in plan. Auto-fix was necessary to complete Task 1.

## Issues Encountered
None beyond the font URL issue documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Page should now load without CSP violations under `default-src 'self'` policy
- All visual elements preserved (font, layout, hover effects, colors)
- All interactive features functional (login, host, join, swipe, matches, genres, solo mode, undo, logout)

## Self-Check: PASSED

All files exist: styles.css, Allura-Regular.woff2, app.js, index.html
All commits found: 86787cb, c6d38c0

---
*Phase: 29-some-other-changes-to-the-site-html-is-causing-an-error-that*
*Completed: 2026-04-26*
