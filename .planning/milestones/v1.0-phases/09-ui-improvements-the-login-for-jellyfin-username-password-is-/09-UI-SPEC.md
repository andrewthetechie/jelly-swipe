---
phase: 09
slug: ui-improvements-the-login-for-jellyfin-username-password-is
status: draft
shadcn_initialized: false
preset: none
created: 2026-04-24
---

# Phase 9 — UI Design Contract

> Flask-served embedded HTML/CSS/JS (`templates/index.html`, mirrored `data/index.html`). No React component library.

---

## Design system

| Property | Value |
|----------|-------|
| Tool | none (embedded styles) |
| Preset | not applicable |
| Component library | none |
| Icon library | none (emoji/text only) |
| Font | Allura (display), system `sans-serif` (body) — existing |

---

## Spacing scale

Declared values (multiples of 4 where new padding introduced):

| Token | Value | Usage |
|-------|-------|-------|
| sm | 8px | Tight UI |
| md | 16px | Default |
| lg | 24px | Section padding |

Exceptions: none for Phase 9 (CSS-only poster containment uses existing card geometry).

---

## Typography

| Role | Size | Weight | Line height |
|------|------|--------|-------------|
| Body | inherited | normal | inherited |
| Menu button | 1.2rem | bold | normal |
| Movie title | 1.8rem | bold | 1.1 |

---

## Color

| Role | Value | Usage |
|------|-------|-------|
| Dominant (60%) | `#111` | Page background |
| Secondary (30%) | `#1a1a1a` | Card backs |
| Accent (10%) | `#e5a00d` | Buttons, titles, borders |
| Letterbox bars (new) | `#000` | Areas beside `object-fit: contain` posters |

Accent reserved for: primary actions, genre highlights, card borders — unchanged from baseline.

---

## Copywriting contract

| Element | Copy |
|---------|------|
| Jellyfin primary CTA (delegate mode) | **Continue** — single verb; no “Login with Jellyfin” when server identity is used |
| Jellyfin interactive fallback (if ever shown) | **Login with Jellyfin** |
| Delegate failure alert | Problem: “Could not use server Jellyfin account.” Next step: “Check server logs and JELLYFIN_* environment variables.” |
| Empty poster / broken thumb | Keep existing alt text behavior |

---

## Interaction contract

### Jellyfin delegate bootstrap

1. On `window.onload`, after existing Plex pin handling, if `mediaProvider === "jellyfin"`: `GET /auth/provider`.
2. If JSON field `jellyfin_browser_auth === "delegate"`: `POST /auth/jellyfin-use-server-identity` with `Content-Type: application/json` and empty body `{}`.
3. On 200: read JSON `userId` (string), persist **only** `localStorage.setItem("provider_user_id", userId)` and `localStorage.setItem("plex_id", userId)` for header compatibility; **remove** `provider_token` and `plex_token` keys if present so the app does not send a stale user token.
4. Hide `#login-section`, show `#main-menu`, call `loadGenres()` — same as legacy post-login path.
5. Never call `prompt()` for username/password on the delegate path.

### Posters

- Primary swipe card and mini-poster grid: full poster visible; letterboxing/pillarboxing acceptable; no horizontal cropping of standard one-sheet artwork.

---

## Registry safety

| Registry | Blocks used | Safety gate |
|----------|-------------|-------------|
| shadcn | none | not required |
| Google Fonts (Allura) | existing `@import` | unchanged |

---

## Checker sign-off

- [ ] Dimension 1 Copywriting: PASS
- [ ] Dimension 2 Visuals: PASS
- [ ] Dimension 3 Color: PASS
- [ ] Dimension 4 Typography: PASS
- [ ] Dimension 5 Spacing: PASS
- [ ] Dimension 6 Registry safety: PASS

**Approval:** pending
