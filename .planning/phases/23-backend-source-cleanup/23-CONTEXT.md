# Phase 23: Backend Source Cleanup - Context

**Gathered:** 2026-04-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Remove all dead Plex route code and stale Plex references from backend Python source files (`jellyswipe/__init__.py`, `jellyswipe/db.py`, `jellyswipe/base.py`). No new features — purely deletion and comment/docstring updates.

</domain>

<decisions>
## Implementation Decisions

### Route deletion
- **D-01:** Delete the `/plex/server-info` route entirely from `jellyswipe/__init__.py` (lines 430–434). Do NOT rename — Phase 24 removes all frontend callers (`fetchPlexServerId()`), so the route becomes dead code.

### db.py stale comments
- **D-02:** Agent's discretion — remove or rewrite the two `plex_id` comments at `jellyswipe/db.py:35` and `:41`. The migration code (`ALTER TABLE ADD COLUMN user_id`) is self-documenting. Comments can be removed entirely or replaced with generic descriptions like "Add user_id column for older databases".

### base.py docstring
- **D-03:** Agent's discretion — update the `fetch_library_image` docstring at `jellyswipe/base.py:41-42` to replace the Plex path reference `/library/metadata/` with the actual Jellyfin validation pattern. The implementation validates against `jellyfin/{id}/Primary` format (see `__init__.py:530` regex and `jellyfin_library.py:363` `_JF_IMAGE_PATH` match).

### Out of scope for this phase
- The `server_info()` abstract method on `base.py:33` and its Jellyfin implementation at `jellyfin_library.py:346` — these are not Plex-specific in implementation and will be evaluated in a later phase if needed.
- The `machineIdentifier` field name in `server_info()` return dict — same reasoning, not blocking.

</decisions>

<canonical_refs>
## Canonical References

### Phase requirements
- `.planning/REQUIREMENTS.md` — SRC-01, SRC-02, SRC-03 requirements and acceptance criteria
- `.planning/ROADMAP.md` § Phase 23 — success criteria (3 items)

### Related source files
- `jellyswipe/__init__.py` — `/plex/server-info` route at line 430, `/proxy` route validation regex at line 530
- `jellyswipe/db.py` — migration comments at lines 35 and 41
- `jellyswipe/base.py` — `LibraryMediaProvider` abstract class with stale docstring at line 42
- `jellyswipe/jellyfin_library.py` — `server_info()` at line 346, `fetch_library_image()` at line 362 (reference for correct Jellyfin path format)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `get_provider()` factory in `__init__.py` — returns the configured `JellyfinLibraryProvider` instance; used throughout routes
- `_JF_IMAGE_PATH` regex in `jellyfin_library.py` — validates Jellyfin image path format; can inform the docstring rewrite

### Established Patterns
- Route deletion: Flask routes are simple `@app.route()` decorators with function bodies; delete the decorator and function together
- Docstring style: Google-style docstrings with brief description + details in base.py
- Comment style: sparse inline comments in db.py migration code

### Integration Points
- `/plex/server-info` route is called from `templates/index.html:403` via `fetch('/plex/server-info')` — Phase 24 handles removing those callers
- `server_info()` method on provider is used only by this route — after route deletion, the method becomes unused (but stays for now)

</code_context>

<specifics>
## Specific Ideas

- The `/proxy` route at `__init__.py:530` already has a correct regex for Jellyfin path validation: `r"^jellyfin/(?:[0-9a-fA-F]{32}|[0-9a-fA-F-]{36})/Primary$"` — this can inform the base.py docstring rewrite
- The db.py comments are in schema migration code that runs on every startup — the code is stable and won't change behavior regardless of comment treatment

</specifics>

<deferred>
## Deferred Ideas

- Rename `server_info()` method or its `machineIdentifier` return field to Jellyfin-idiomatic names — deferred to a future cleanup pass
- Consider whether `server_info()` is needed at all after Phase 24 removes all callers — evaluate post-Phase 24

</deferred>

---

*Phase: 23-backend-source-cleanup*
*Context gathered: 2026-04-26*
