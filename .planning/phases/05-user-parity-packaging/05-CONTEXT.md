# Phase 5: User parity & packaging - Context

**Gathered:** 2026-04-22  
**Status:** Ready for planning

<domain>
## Phase Boundary

Ship **per-user parity in Jellyfin mode** (matches, history, delete, undo) keyed to a **Jellyfin-derived user identifier**, **list-add** to a Jellyfin-side collection when the client is authenticated, **front-end / server header contract** so Plex-only assumptions are not required in Jellyfin mode (or are explicitly bridged), and **packaging** so Docker/CI and `requirements.txt` stay green with any new dependencies (JUSR-01 — JUSR-04).

**Out of scope:** Renaming DB columns to neutral names (**OPS-01** / v2 backlog), neutral `/media/server-info` route rename unless already trivial.

</domain>

<decisions>
## Implementation Decisions

### User identity and storage (JUSR-01)

- **D-01:** Keep existing SQLite columns **`plex_id`** (and related query params) as the **per-user partition key** in both modes; in Jellyfin mode the value stores the **Jellyfin user id** (string GUID from the authenticated session). Document the semantic overload in **README** (same column name, different provider meaning).
- **D-02:** Server reads Jellyfin end-user identity from **`Authorization: MediaBrowser … Token="<user_access_token>"`** when present, and/or a dedicated header **`X-Emby-UserId`** / **`X-Jellyfin-User-Id`** if the client already sends it — **defaults:** prefer resolving the **user id** from the **user access token** via Jellyfin **`/Users/Me`** (or equivalent) on each request that needs `plex_id`, with minimal caching **Claude’s discretion** (short TTL or none for v1).

### List / watchlist parity (JUSR-02)

- **D-03:** Implement **“add matched title to user list”** in Jellyfin mode using Jellyfin’s **authenticated user** APIs (favorites or custom collection — **defaults:** **favorites** / **`IsFavorite`** style flow if a simple stable API exists; otherwise smallest viable **user playlist** or **collection** mutation documented in README).
- **D-04:** Reject list-add with **401/400** and a clear JSON message when no user token is supplied (no silent fallbacks to admin token).

### Front-end contract (JUSR-03)

- **D-05:** **Defaults (minimal FE churn):** Client may continue sending **`X-Plex-User-ID`** in Jellyfin mode carrying the **Jellyfin user id string** once obtained from a Jellyfin-specific auth path; server treats it as **provider user id** when `MEDIA_PROVIDER=jellyfin`. Document explicitly. If the team prefers a neutral header later, add **`X-Provider-User-Id`** as an **optional alias** the server also accepts in Jellyfin mode only (**Claude’s discretion** whether to implement alias in Phase 5 or defer).

### Packaging (JUSR-04)

- **D-06:** Any new Python deps must appear in **`requirements.txt`** and remain compatible with the **existing Dockerfile** (`pip install -r requirements.txt`). **CI:** `.github/workflows/docker-image.yml` must stay green.

### Discussion note (`--chain` + `defaults`)

- **D-07:** Invoked as **`/gsd-discuss-phase 5 --chain`** after **`/gsd-next --chain`**; gray areas resolved with **`[chain] defaults`** per Phases 2–4.

### Claude's Discretion

- Exact Jellyfin endpoints for favorites/list mutation, small caching of `/Users/Me`, and whether to add **`X-Provider-User-Id`** alias in this phase.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Planning / product

- `.planning/PROJECT.md` — Either-or instance, security (no secrets in logs/errors).
- `.planning/REQUIREMENTS.md` — **JUSR-01** — **JUSR-04**.
- `.planning/ROADMAP.md` — Phase 5 goal and success criteria.

### Prior phases

- `.planning/phases/04-jellyfin-library-media/04-CONTEXT.md` — Library parity, proxy path scheme.
- `.planning/phases/03-jellyfin-authentication-http-client/03-CONTEXT.md` — Admin/server Jellyfin token vs future user token.
- `.planning/phases/02-media-provider-abstraction/02-CONTEXT.md` — Provider boundary; watchlist was Plex-specific in `app.py`.

### Implementation

- `app.py` — `/matches`, `/watchlist/add`, `/undo`, `/matches/delete`, `/room/swipe`, auth routes, `MEDIA_PROVIDER` branching.
- `templates/` / `static/` — headers and fetch calls if FE changes are required.

### Codebase intelligence

- `.planning/codebase/INTEGRATIONS.md` — Current auth and identity patterns.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable assets

- **Plex pin + `X-Plex-User-ID`** flows in `app.py` — mirror outcomes for Jellyfin with different token acquisition.
- **`plex_id` columns** — already partition per-user rows; reuse for Jellyfin user id string.

### Established patterns

- **JSON errors** — preserve `{ "error": "..." }` style; never echo secrets.

### Integration points

- **Watchlist route** — Jellyfin branch must not call Plex-only `MyPlexAccount` paths.

</code_context>

<specifics>
## Specific Ideas

- README should include a **short “Jellyfin user id header”** section for operators and client authors.

</specifics>

<deferred>
## Deferred Ideas

- **OPS-01** — Rename `plex_id` column to neutral name (v2).

### Reviewed Todos (not folded)

- None.

</deferred>

---

*Phase: 05-user-parity-packaging*  
*Context gathered: 2026-04-22*
