# Phase 3: Jellyfin authentication & HTTP client - Context

**Gathered:** 2026-04-22  
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver a **server-side Jellyfin session**: obtain and hold an **access token** (or equivalent) from operator-configured credentials, expose a small **authenticated HTTP client** for the Jellyfin REST API, and integrate with **`get_provider()`** so Jellyfin mode is no longer blocked at the factory with the Phase 2 “not implemented” guard (JAUTH-01 — JAUTH-03).

**In scope for Phase 3:** Token acquisition (API key and/or username+password per existing env contract), secure handling and error surfaces without leaking secrets, **reset/re-login** behavior aligned with the Plex provider’s `reset()` story, and proof that the token can authorize at least one **`/Items`** (or documented equivalent) call.

**Explicitly Phase 4+:** Full `LibraryMediaProvider` parity (deck JSON, genres, proxy thumbs, TMDB chain, server-info shape) — this phase may ship a `JellyfinLibraryProvider` skeleton that satisfies auth + HTTP while **stubbing or minimally implementing** library methods only as needed to avoid regressing startup and **fail-fast** expectations until Phase 4 lands.

</domain>

<decisions>
## Implementation Decisions

### Credentials and token acquisition

- **D-01:** Reuse **Phase 1 env contract**: non-empty `JELLYFIN_URL`; either **`JELLYFIN_API_KEY`** **or** **`JELLYFIN_USERNAME` + `JELLYFIN_PASSWORD`** (same validation rules as `app.py` today).
- **D-02:** If **API key** is configured, authenticate using the server-supported **header-based** pattern (prefer modern **`Authorization: MediaBrowser …`** / documented Jellyfin 10.8+ approach over query-string secrets). If **username/password** is configured, use **`/Users/AuthenticateByName`** (or the current stable equivalent from official Jellyfin REST docs) to obtain an **access token** for subsequent requests.
- **D-03:** Do **not** add new user-facing env variable names in Phase 3 unless research proves an unavoidable gap — extend README only to document behavior and version assumptions.

### Module layout and factory

- **D-04:** Implement Jellyfin client and provider under **`media_provider/`** as a **dedicated module** (e.g. `media_provider/jellyfin_library.py` holding HTTP + auth, with a `JellyfinLibraryProvider` class implementing `LibraryMediaProvider` or a thin façade that composes a client used by the provider — exact file split is **Claude’s discretion**).
- **D-05:** Update **`media_provider/factory.py`** so when `MEDIA_PROVIDER=jellyfin`, `get_provider()` returns the Jellyfin concrete implementation **without** raising the Phase 2 placeholder error. **`reset()`** must clear Jellyfin session/token state the same way it invalidates Plex.

### Token storage and reconnection

- **D-06:** Keep access token **in-memory** on the provider/client instance only (**no** on-disk token cache in v1).
- **D-07:** Mirror the **Plex** pattern: on transport/auth failure paths that indicate a **dead session** (e.g. **401** from Jellyfin after a successful login once worked), **`reset()`** clears cached token/client state; the next `get_provider()` use **re-authenticates** once (bounded retry — same spirit as Plex `reset` + retry).

### Errors, logging, and observability

- **D-08:** JSON errors and HTTP responses must **never** include the raw **access token**, **API key**, or **password** (JAUTH-03). Prefer messages like **“Jellyfin authentication failed”** with optional non-sensitive detail (HTTP status, error code name).
- **D-09:** Application logs must not print secrets; if logging response bodies on failure, **truncate/redact** first.

### Verification and docs

- **D-10:** **Manual test notes** (README section or `.planning` phase verification snippet) must include **one** explicit exercise of **token refresh / re-login**: e.g. revoke API key or use wrong password, confirm clear error, restore valid creds, confirm `/Items` succeeds again (roadmap success criterion 3).
- **D-11:** Document **Jellyfin 10.8+** assumption and header/token behavior in **README** in the same pass as code (align with `PROJECT.md` compatibility).

### Discussion note (`--chain`)

- **D-12:** User invoked **`/gsd-discuss-phase 3 --chain`**; gray areas were not interactively stepped through in this session. Per the **same `defaults` convention** used in Phase 2 (`02-CONTEXT.md` D-11), **recommended** options above are treated as **locked** for planning. Re-run `/gsd-discuss-phase 3` without `--chain` if you want to revise any decision before implementation.

### Claude's Discretion

- Exact **REST paths** and **payload field names** from the live Jellyfin OpenAPI for the server version targeted.
- Whether **`requests.Session`** vs plain **`requests`** per call.
- Placement of small **private helpers** (e.g. `_post_json`) vs a single **`JellyfinClient`** class.
- How much of **`LibraryMediaProvider`** is **stubbed** vs **real** in Phase 3 as long as Phase boundary and roadmap success criteria are met.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Planning / product

- `.planning/PROJECT.md` — Security expectations (no token logging, HTTPS), either-or provider, Jellyfin REST reference.
- `.planning/REQUIREMENTS.md` — **JAUTH-01**, **JAUTH-02**, **JAUTH-03** (exact wording).
- `.planning/ROADMAP.md` — Phase 3 goal and success criteria (token, `/Items`, errors, manual re-login exercise).

### Prior phase contracts

- `.planning/phases/01-configuration-startup/01-CONTEXT.md` — `MEDIA_PROVIDER`, Jellyfin env validation (operator contract).
- `.planning/phases/02-media-provider-abstraction/02-CONTEXT.md` — `LibraryMediaProvider`, `media_provider/` layout, factory singleton, **Phase 2 fail-fast** story superseded in Jellyfin mode by Phase 3 factory change (document migration in plans).

### Implementation

- `media_provider/base.py` — Provider ABC.
- `media_provider/factory.py` — `get_provider` / `reset` selection logic (must change for Jellyfin).
- `media_provider/plex_library.py` — Reference for retry/`reset` parity.
- `app.py` — Startup env validation and any Jellyfin-specific route behavior already present.

### Codebase intelligence

- `.planning/codebase/INTEGRATIONS.md` — Current external HTTP patterns (Plex, TMDB).
- `.planning/codebase/ARCHITECTURE.md` — Monolith, singleton provider pattern.

### External

- Official Jellyfin REST / OpenAPI documentation for the target major version — **must** be consulted during research/planning for auth header and login routes.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable assets

- **`media_provider/factory.py`** — Central switch for `MEDIA_PROVIDER`; today returns `PlexLibraryProvider` only and raises for `jellyfin`.
- **`media_provider/plex_library.py`** — Template for **lazy imports**, **instance `reset()`**, and **retry-after-reset** around server calls.
- **`app.py` startup** — Already validates `JELLYFIN_URL` and credential bundles for `jellyfin` mode.

### Established patterns

- **JSON errors** — `jsonify({'error': str(e)})` in routes; Phase 3 code must ensure `str(e)` never contains token material (catch and wrap at Jellyfin client boundary if needed).
- **Provider `reset()`** — Called from factory `reset()`; Jellyfin must participate symmetrically with Plex.

### Integration points

- **Factory** — Only entry point for `get_provider()` used by routes; Jellyfin auth work lands behind the returned instance’s methods or an internal session object.

</code_context>

<specifics>
## Specific Ideas

- Prefer **header** auth and **HTTPS** URLs per `PROJECT.md` constraints.
- Phase 3 **proves** `/Items` (or documented subset) works; **deck parity** remains the headline of Phase 4.

</specifics>

<deferred>
## Deferred Ideas

- **Full library parity** (genres, deck shape, `/proxy` Jellyfin paths, TMDB id chain) — Phase 4 (**JLIB-***).
- **Per-user Jellyfin identity / watchlist parity** — Phase 5 (**JUSR-***).
- **Neutral `/media/server-info` route** — still deferred from Phase 2 unless Phase 4 pulls it in.

### Reviewed Todos (not folded)

- None — `todo.match-phase` returned no matches for phase 3.

</deferred>

---

*Phase: 03-jellyfin-authentication-http-client*  
*Context gathered: 2026-04-22*
