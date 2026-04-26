# Phase 29: Fix CSP Inline Style Errors - Context

**Gathered:** 2026-04-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix Content-Security-Policy violations in `jellyswipe/templates/index.html` that block inline styles under a `default-src 'self'` CSP policy, causing the page to not load properly. This involves removing all inline `style=` attributes, replacing JS hover handlers with CSS `:hover`, and self-hosting the Google Fonts dependency. No CSP header changes in the Flask app — the fix is entirely in the HTML template.

**In scope:**
- Refactor all inline `style=` attributes to CSS classes in the template's `<style>` block
- Replace `onmouseover`/`onmouseout` handlers that set `this.style.boxShadow` with CSS `:hover` pseudo-classes
- Self-host the Allura font locally in `static/fonts/` instead of loading from Google Fonts CDN
- Remove the `@import url('https://fonts.googleapis.com/...')` and reference the local font

**Out of scope:**
- Adding or modifying CSP headers in the Flask app
- Changes to `data/index.html` (already deleted on the main branch)
- Changes to Python backend code
- External font CDN configuration

</domain>

<decisions>
## Implementation Decisions

### CSP Fix Strategy
- **D-01:** Refactor all inline `style=` attributes to named CSS classes — no CSP header changes in the Flask app
- **D-02:** CSS classes go in the existing `<style>` block in `index.html` (or a separate `.css` file in `static/` — agent's discretion)
- **D-03:** The `default-src 'self'` CSP comes from infrastructure/reverse proxy, not from the app — do NOT add a CSP header in Flask

### Hover Effects
- **D-04:** Replace the 3 `onmouseover`/`onmouseout` inline handlers that set `this.style.boxShadow` with CSS `:hover` pseudo-classes
- **D-05:** This eliminates inline JS event handlers entirely for those elements — cleaner and CSP-compliant by default
- **D-06:** Affected elements: host-btn, join-btn, history-btn (each has onmouseover/onmouseout setting boxShadow)

### Google Fonts
- **D-07:** Download the Allura font and host it locally in `static/fonts/` (e.g., `static/fonts/Allura-Regular.woff2`)
- **D-08:** Replace `@import url('https://fonts.googleapis.com/css2?family=Allura&display=swap')` with a local `@font-face` rule in the `<style>` block
- **D-09:** This removes the external CDN dependency entirely — no `font-src` directive needed

### Template Scope
- **D-10:** Only `jellyswipe/templates/index.html` needs changes — `data/index.html` is already deleted on the main branch
- **D-11:** Do NOT touch `data/index.html` in this worktree

### Inline Script Block
- **D-12:** The inline `<script>` block contains application logic (swipe handling, room management, SSE, etc.) — not just hover handlers
- **D-13:** The CSP error is specifically about `style-src-elem` blocking inline styles, not about script-src — verify whether the inline `<script>` also violates the CSP before deciding whether to externalize it
- **D-14:** If inline `<script>` also violates CSP, externalize it to `static/app.js` (agent's discretion based on what the CSP actually blocks)

### the agent's Discretion
- Whether CSS classes go in the existing `<style>` block or a new `static/styles.css` file
- Naming convention for new CSS classes (semantic vs descriptive)
- Whether to also externalize the inline `<script>` block to a `.js` file (if it also violates CSP)
- Font file format (woff2 preferred, woff fallback)
- Whether to add `font-display: swap` in the `@font-face` rule

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Target Template
- `jellyswipe/templates/index.html` — The single file being modified; contains all inline styles, hover handlers, Google Fonts import, and the inline `<style>` and `<script>` blocks

### Flask App Entry Point
- `jellyswipe/__init__.py` — Contains `create_app()`, route definitions, `index()` route renders `index.html`; check for any existing CSP or security headers

### Static Assets
- `jellyswipe/static/` — Directory where the self-hosted font file should be placed (e.g., `jellyswipe/static/fonts/Allura-Regular.woff2`)
- `jellyswipe/static/manifest.json` — PWA manifest that references static assets

### Prior Phase Decisions
- `.planning/phases/28-coverage-enforcement/28-CONTEXT.md` — Coverage threshold context (relevant if tests need updating)

### Codebase Architecture
- `.planning/codebase/ARCHITECTURE.md` — Template rendering flow: `GET /` → `render_template('index.html')`, inline CSS and JS in single HTML file
- `.planning/codebase/STRUCTURE.md` — `templates/` directory layout, `static/` directory for assets

</canonical_refs>

<code_context>
## Existing Code Insights

### Current State of index.html
- **34 inline `style=` attributes** scattered throughout the template
- **3 dynamic JS style manipulations**: `this.style.boxShadow` in `onmouseover`/`onmouseout` on host-btn, join-btn, history-btn
- **1 inline `<style>` block** (~190 lines of CSS) starting at line 15
- **1 inline `<script>` block** (~320 lines of JS) containing all application logic
- **1 Google Fonts import**: `@import url('https://fonts.googleapis.com/css2?family=Allura&display=swap')` at line 16
- **JS-generated inline styles**: JavaScript template literals in match history rendering also inject `style=` attributes (lines 559-611)

### Reusable Assets
- Existing `<style>` block already has CSS classes (`.menu-btn`, `.plex-yellow`, `.hidden`, `.stats-row`, etc.) — new classes should follow the same naming style
- `jellyswipe/static/` directory already serves static files via Flask's built-in static file handler

### Established Patterns
- Single-file SPA: all HTML/CSS/JS in one template file
- CSS uses simple class names, no preprocessor, no framework
- Static assets served from `jellyswipe/static/` via Flask

### Integration Points
- `jellyswipe/__init__.py:128-129` — `@app.route('/')` renders `index.html` with `media_provider="jellyfin"`
- Flask serves static files from `jellyswipe/static/` automatically at `/static/` path
- Font file in `static/fonts/` would be accessible at `/static/fonts/Allura-Regular.woff2`

</code_context>

<specifics>
## Specific Ideas

- The CSP error specifically mentions `style-src-elem` blocking inline styles — the fix must ensure no inline `style=` attributes remain in the rendered HTML
- The hover effect on buttons (glowing box-shadow on host/join/history buttons) should look identical after switching to CSS `:hover` — same `rgba(229, 160, 13, 0.7)` values
- JS-generated HTML in match history (template literals with inline styles around lines 559-611) also needs CSS class conversion

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 29-some-other-changes-to-the-site-html-is-causing-an-error-that*
*Context gathered: 2026-04-26*
