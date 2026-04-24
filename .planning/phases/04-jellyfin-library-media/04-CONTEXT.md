# Phase 4: Jellyfin library & media - Context

**Gathered:** 2026-04-22  
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver **Jellyfin library parity** for the core swipe experience: same **per-movie JSON** the UI already expects, **genre list + deck refetch** behavior aligned with Plex (including **Recently Added** ordering), **thumbs through the Flask app** with **strict path validation** (no open proxy), **TMDB trailer/cast** using Jellyfin-backed `movie_id`, and **server id + display name** for UI parity with `/plex/server-info` (JLIB-01 — JLIB-05).

**Out of scope here:** Per-user Jellyfin identity, watchlist parity, and neutral route renames (**Phase 5** / backlog). Plex mode behavior stays on `PlexLibraryProvider` unchanged.

</domain>

<decisions>
## Implementation Decisions

### Identity and card JSON

- **D-01:** Card field **`id`** is the Jellyfin item **`Id`** (GUID string). It is carried through **`/get-trailer`**, **`/cast`**, swipes, and DB rows the same way Plex uses stringified rating keys today.
- **D-02:** Map Jellyfin fields to the existing card shape: **`title`** ← `Name`, **`summary`** ← `Overview`, **`year`** ← `ProductionYear`, **`rating`** ← `CommunityRating` (or `CriticRating` when community missing), **`duration`** ← humanized **`RunTimeTicks`** (same hour/minute spirit as Plex), **`thumb`** ← **`/proxy?path=jellyfin/{ItemId}/Primary`** (single allowlisted pattern for Phase 4).

### Genres and deck semantics

- **D-03:** **Movies library** is the first user view with **`CollectionType`** equal to **`movies`** (case-insensitive) from **`/Users/{userId}/Views`** after resolving **`/Users/Me`**. If none found, fail with a clear configuration error (operator must expose a Movies-type library).
- **D-04:** **Genre list** comes from **`/Items/Filters`** (or **`/Genres`** fallback) scoped to that library + `IncludeItemTypes=Movie`; normalize **Science Fiction** display label to **Sci-Fi** to match Plex deck behavior.
- **D-05:** **Deck fetch** mirrors Plex rules: **All** + random genre use **random** ordering with caps like Plex; **Recently Added** uses **date descending**, **no shuffle**; named genres filter by Jellyfin’s **`Genres`** query parameter with Sci-Fi ↔ Science Fiction mapping identical in spirit to Plex.

### Images and `/proxy`

- **D-06:** Extend **`/proxy`** so **`MEDIA_PROVIDER=jellyfin`** serves images via the provider; **`503`** when Jellyfin is not configured; **`403`** unless **`path`** matches strict **`jellyfin/{id}/Primary`** allowlist shape where `{id}` is either canonical UUID or 32-hex item id (`^jellyfin/(?:[0-9a-fA-F]{32}|[0-9a-fA-F-]{36})/Primary$`) (JLIB-03, JLIB-05 spirit — no arbitrary upstream paths).
- **D-07:** Upstream fetch uses authenticated **`GET /Items/{id}/Images/Primary`** (with sensible `maxWidth`/`maxHeight` query params optional — Claude’s discretion).

### TMDB and server info

- **D-08:** **`resolve_item_for_tmdb`** uses **`GET /Items/{id}`** (authenticated) and returns an object exposing **`.title`** and **`.year`** for existing `app.py` TMDB routes (JLIB-04).
- **D-09:** **`server_info()`** for Jellyfin returns **`{ machineIdentifier, name }`** using **authenticated `/System/Info`** when available, else fall back to **`/System/Info/Public`** — stable **`ServerId`/`Id`** mapped to **`machineIdentifier`** for UI parity (JLIB-05). Route path stays **`/plex/server-info`** in Phase 4 (neutral rename remains deferred).

### Resilience

- **D-10:** On **401** from Jellyfin after a successful session, **`reset()`** + single **re-auth** retry at the **HTTP helper** layer (same spirit as Plex `reset` + retry), without unbounded loops.

### Discussion note (`--chain` + `defaults`)

- **D-11:** User ran **`/gsd-discuss-phase 4 --chain`**; gray areas resolved with **`[chain] defaults`** (recommended options), matching Phases 2–3. Re-run discuss without `--chain` to revisit any decision.

### Claude's Discretion

- Exact **Jellyfin query parameter** sets per server version quirks, **`maxWidth`** on images, and small helper decomposition inside `jellyfin_library.py`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Planning / product

- `.planning/PROJECT.md` — HTTPS, no token logging, minimal churn.
- `.planning/REQUIREMENTS.md` — **JLIB-01** through **JLIB-05**.
- `.planning/ROADMAP.md` — Phase 4 goal and success criteria.

### Prior phases

- `.planning/phases/02-media-provider-abstraction/02-CONTEXT.md` — `LibraryMediaProvider`, `/proxy` Plex contract, card JSON shape.
- `.planning/phases/03-jellyfin-authentication-http-client/03-CONTEXT.md` — Jellyfin auth, `MediaBrowser` headers, Phase 3 factory behavior.

### Implementation

- `media_provider/base.py` — Provider contract.
- `media_provider/jellyfin_library.py` — Jellyfin implementation surface.
- `media_provider/plex_library.py` — Parity reference for deck/genre semantics.
- `app.py` — `/proxy`, `/plex/server-info`, `/get-trailer`, `/cast`, room + `/movies` + `/genres`.

### Codebase intelligence

- `.planning/codebase/INTEGRATIONS.md` — External HTTP patterns.

### External

- Official Jellyfin REST/OpenAPI for the operator’s server version — **must** be consulted for exact filter and image sub-routes if behavior diverges from 10.8 defaults.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable assets

- **`JellyfinLibraryProvider.ensure_authenticated`** and **`_media_browser_header`** — extend with cached user/library ids and JSON helpers.
- **`app.py` `proxy()`** — branch on `MEDIA_PROVIDER` alongside existing Plex checks.

### Established patterns

- **Plex card keys** — `id`, `title`, `summary`, `thumb`, `rating`, `duration`, `year`.
- **Try/except → JSON errors** in routes; do not leak secrets in `str(e)` for auth paths.

### Integration points

- **`get_provider()`** — all library routes already flow through the provider for deck/genres/images/trailer/cast/server info.

</code_context>

<specifics>
## Specific Ideas

- Keep **one** `/proxy` route; encode Jellyfin thumbs with the **`jellyfin/{guid}/Primary`** path scheme for easy validation.

</specifics>

<deferred>
## Deferred Ideas

- **Neutral `/media/server-info`** — still deferred (Phase 2 note); Jellyfin uses same JSON keys via `server_info()`.
- **Per-user headers / watchlist** — Phase 5 (**JUSR-***).

### Reviewed Todos (not folded)

- None.

</deferred>

---

*Phase: 04-jellyfin-library-media*  
*Context gathered: 2026-04-22*
