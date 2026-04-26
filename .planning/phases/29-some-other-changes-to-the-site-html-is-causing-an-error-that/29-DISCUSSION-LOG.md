# Phase 29: Fix CSP Inline Style Errors - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-26
**Phase:** 29-some-other-changes-to-the-site-html-is-causing-an-error-that
**Areas discussed:** CSP Fix Strategy, Hover Effects, Google Fonts, Template Scope

---

## CSP Fix Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Refactor inline styles to CSS classes | Move all 34 `style=` attributes to named CSS classes; no CSP header changes in Flask | ✓ |
| Add explicit CSP header in Flask | Set `Content-Security-Policy` header with `style-src 'unsafe-inline'` or nonce-based policy | |
| Both — refactor + add CSP header | Move styles to CSS AND set an explicit CSP policy for defense in depth | |

**User's choice:** Refactor all inline `style=` attributes to CSS classes. No CSP header changes in the app.
**Notes:** The `default-src 'self'` CSP comes from infrastructure/reverse proxy, not from Flask. Fixing the HTML is the clean solution.

---

## Hover Effects

| Option | Description | Selected |
|--------|-------------|----------|
| CSS `:hover` pseudo-classes | Replace onmouseover/onmouseout with CSS :hover rules for box-shadow glow effect | ✓ |
| Nonce-based CSP with inline handlers | Generate CSP nonces per-request and apply to inline event handlers | |
| `'unsafe-hashes'` in CSP | Allow specific style attribute hashes in the CSP directive | |

**User's choice:** Replace 3 `onmouseover`/`onmouseout` handlers with CSS `:hover` pseudo-classes.
**Notes:** Affected elements: host-btn, join-btn, history-btn. Same visual result (glowing box-shadow), cleaner code, eliminates inline JS.

---

## Google Fonts

| Option | Description | Selected |
|--------|-------------|----------|
| Self-host font in `static/fonts/` | Download Allura .woff2, add `@font-face` rule, remove Google CDN import | ✓ |
| Add `font-src fonts.googleapis.com` to CSP | Allow the external CDN through the CSP policy | |
| Switch to system font | Remove Allura entirely, use a system sans-serif fallback | |

**User's choice:** Self-host the Allura font locally in `static/fonts/`.
**Notes:** Removes external CDN dependency entirely. No `font-src` directive needed.

---

## Template Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Fix `jellyswipe/templates/index.html` only | `data/index.html` is deleted on main branch | ✓ |
| Fix both templates | Synchronize changes across both files | |

**User's choice:** Only fix `jellyswipe/templates/index.html`.
**Notes:** `data/index.html` is already deleted on the main branch — no need to touch it.

---

## Agent's Discretion

- Whether CSS classes go in existing `<style>` block or a new `static/styles.css` file
- CSS class naming convention
- Whether to externalize inline `<script>` to a `.js` file (if it also violates CSP)
- Font file format (woff2 preferred)
- Whether to add `font-display: swap` in `@font-face`

## Deferred Ideas

None — discussion stayed within phase scope.
