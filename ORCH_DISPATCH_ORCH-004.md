## Ticket
- ID: ORCH-004
- Title: Expand JellyfinLibraryProvider for TV show libraries and multi-library fetching
- State: In Progress
- Risk Score: 4
- Rework Loop Count: 1
- Linked PR: https://github.com/andrewthetechie/jelly-swipe/pull/43

### Description
Expand the Jellyfin provider from first-movie-library-only to all eligible libraries for both movies and TV shows. This is the core data-fetching change.

**Files to modify:**
- `jellyswipe/jellyfin_library.py` — Major changes to `JellyfinLibraryProvider`:
  - Replace `_movies_library_id()` (single cached ID) with `_library_ids_for_type(collection_type: str) -> list[str]` that returns all matching library IDs. Cache per collection type.
  - Add `_series_to_card(it: dict) -> dict` mapping method for TV Series items: extracts `Id`, `Name`, `Overview`, `ProductionYear`, and optionally `ChildCount` (season count). Sets `media_type: "tv_show"`. No duration mapping.
  - Update `_item_to_card` to set `media_type: "movie"` on each card.
  - Update `fetch_deck(genre_name)` signature to `fetch_deck(media_types: list[str], genre_name: str | None = None) -> list[dict]`. When `media_types` contains `"movie"`, query all movie libraries. When it contains `"tv_show"`, query all TV libraries with `IncludeItemTypes=Series`. For each type, query all eligible libraries and merge results.
  - Update `list_genres()` to query genres from both movie and TV libraries, return deduplicated union.
  - `_genre_cache` should be invalidated when the media type scope changes (or just not cached across different scopes).

- `jellyswipe/base.py` — Update `LibraryMediaProvider` abstract class:
  - `fetch_deck` docstring/signature updated to reflect `media_types` parameter.

**Jellyfin API notes:**
- TV libraries have `CollectionType: "tvshows"` (not `"tv"` or `"tvshows"` — verify).
- Series items use `IncludeItemTypes=Series` in `/Items` queries.
- Series items have `Type: "Series"`, and may expose `ChildCount` (number of seasons).
- Genre queries for TV use the same `/Items/Filters` endpoint with `IncludeItemTypes=Series`.


### Acceptance Criteria
- `_movies_library_id()` is replaced by a generalized method that returns library IDs for a given collection type (e.g., `movies`, `tvshows`).
- Provider discovers all libraries with `CollectionType=movies` and all with `CollectionType=tvshows` (not just the first match).
- `fetch_deck(media_types, genre_name)` fetches from all eligible libraries for each requested media type. TV show queries use `IncludeItemTypes=Series` and appropriate `ParentId` for each TV library.
- TV show cards include: `id`, `title`, `summary`, `thumb`, `year`, `media_type: "tv_show"`. No `duration`, no `rating` from runtime. Optionally include `season_count` if Jellyfin exposes it (e.g., `ChildCount` or similar field on Series items).
- Movie cards include the existing fields plus `media_type: "movie"`.
- `list_genres()` queries genres from all eligible movie AND TV libraries, returns deduplicated sorted union.
- If no library exists for a requested type (e.g., no TV library on server), `fetch_deck` returns an empty list for that type rather than raising.


### File Paths
jellyswipe/jellyfin_library.py, jellyswipe/base.py

### Test Expectations
- `fetch_deck(media_types=["movie"])` returns only cards with `media_type: "movie"` (same behavior as before).
- `fetch_deck(media_types=["tv_show"])` returns only cards with `media_type: "tv_show"` — no episodes, only series-level items.
- `fetch_deck(media_types=["movie", "tv_show"])` returns cards of both types.
- TV cards have `media_type: "tv_show"`, contain `title`, `summary`, `thumb`, `year`, and optionally `season_count`. They do NOT contain `duration`.
- Movie cards have `media_type: "movie"` with all existing fields.
- `list_genres()` returns a deduplicated union of movie and TV genres.
- When no TV library exists on the Jellyfin server, `fetch_deck(media_types=["tv_show"])` returns `[]` without raising.
- `fetch_deck(media_types=["movie"], genre_name="Sci-Fi")` applies genre filter to movie libraries only.
- `fetch_deck(media_types=["tv_show"], genre_name="Drama")` applies genre filter to TV libraries only.

## Comments
- **router**: Agent exited with code 0 without completing. Moved to Needs Human Review.
- **router**: Agent exited with code -2 without completing. Moved to Needs Human Review.
- **router**: ## Needs Human Review — escalated by router

**Agent:** coder  |  **Exit code:** 0  |  **Rework loops:** 0

**Reason:** The agent exited without moving this ticket to the expected next state.

**To resume:** move this ticket to `Rework` once the issues above are addressed.
- **coder**: ## Implementation Complete

**Changes:**
- Expanded `JellyfinLibraryProvider` to support TV show libraries and multi-library fetching
- Replaced `_movies_library_id()` with `_library_ids_for_type(collection_type)` returning all matching library IDs
- Added `_series_to_card()` method for TV Series items with `media_type: "tv_show"` and optional `season_count`
- Updated `fetch_deck(media_types, genre_name)` to fetch from all eligible libraries for each requested media type
- Updated `list_genres()` to query genres from both movie and TV libraries, returning deduplicated union
- Updated call sites in `room_lifecycle.py` and `conftest.py` to use new signature
- Added 5 new tests for TV show functionality

**Validation:**
- `uv run pytest tests/` - 336 tests passed
- `ruff check jellyswipe/` - pre-existing warnings only (no new issues)
- `gitnexus_detect_changes` - confirmed changes scoped to ticket

**Files modified:**
- `jellyswipe/base.py` - Updated abstract method signature
- `jellyswipe/jellyfin_library.py` - Major implementation changes
- `jellyswipe/services/room_lifecycle.py` - Updated call sites
- `tests/conftest.py` - Updated FakeProvider
- `tests/test_jellyfin_library.py` - Added TV show tests

## Pull Request
- URL: https://github.com/andrewthetechie/jelly-swipe/pull/43

## Workflow Instructions
- Agent Role: reviewer
- Current State (pre-dispatch): In Progress
  Note: ticket will read as 'In Progress' at runtime — this is normal.
- Target State: Ready to Merge
- Step Budget: 50 (trigger continuation comment at step 45)
- Working Directory: /home/andrew/jelly-swipe/.orchestra/worktrees/ORCH-004
- **All commands must run from the working directory above.** Never `cd` outside it. All file paths are relative to this directory.