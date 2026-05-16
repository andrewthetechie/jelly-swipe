# Extract `jellyfin_media_item` — MediaItem transformation and genre alias locality

## Problem Statement

`JellyfinLibraryProvider` is a 586-line class that mixes seven distinct concerns: HTTP transport, authentication state, in-process caching, MediaItem transformation, genre alias normalisation, query orchestration, and image proxying. The class earns its keep overall, but the concerns are interleaved rather than layered — MediaItem transformation logic (`_item_to_card`, `_series_to_card`) and the genre alias rule ("Science Fiction" ↔ "Sci-Fi") are buried in the middle of auth retry loops and cache management.

From the developer's perspective this creates two concrete problems:

1. **Navigation friction.** When a card field is wrong or a genre is missing, the developer must open a 586-line file and context-switch through transport machinery to find 20 lines of domain logic. There is no file to open that says "this is where MediaItems are built."

2. **Genre alias duplication.** The alias rule between Jellyfin's canonical name ("Science Fiction") and the display name ("Sci-Fi") appears in three separate inline one-liners (in `list_genres`, `fetch_deck`, and `_fetch_items_for_library`). One conceptual rule lives in three places; any change must be applied three times.

Neither problem is blocked by an ADR. The [ADR 0001](../adr/0001-remove-username-password-auth.md) cleanup and [PRD 007](./007-shallow-module-cleanup.md) regex deduplication work are complementary and do not constrain this extraction.

## Solution

Extract a new `jellyfin_media_item` module containing only the pure, side-effect-free logic that transforms raw Jellyfin API response dicts into MediaItems and normalises genre names for display and query. `JellyfinLibraryProvider` is unchanged in responsibility — it continues to own HTTP transport, auth state, caching, and query orchestration — but it delegates all MediaItem construction and genre name translation to the new module.

The new module has no imports from any HTTP library, no imports from `jellyfin_library`, and no mutable state. It can be read, understood, and tested in complete isolation from the Jellyfin network layer.

## User Stories

1.  As a developer debugging a wrong card field (e.g. duration is blank, rating is missing), I want to open a single focused file that contains only MediaItem transformation logic, so that I can find and fix the issue without scanning auth retry code.
2.  As a developer adding a new MediaItem field (e.g. `genre_tags`), I want to make the change in one place, so that the transformation contract is not scattered across the codebase.
3.  As a developer reading `jellyfin_library.py`, I want the file to be about HTTP, auth, and query orchestration, so that I can understand the Jellyfin client without also processing domain transformation rules.
4.  As a developer updating the "Sci-Fi" display alias, I want to change one definition, so that `list_genres` and `fetch_deck` are guaranteed to agree.
5.  As a developer adding a new genre alias (e.g. "Animation" → "Animated"), I want a single place to add the rule, so that outbound (display) and inbound (query) translations stay in sync automatically.
6.  As a developer writing a test for MediaItem field formatting (e.g. runtime display "1h 45m"), I want to call a pure function with a plain dict, so that the test requires no HTTP mock and no provider setup.
7.  As a developer writing a test for genre alias round-tripping, I want to call `display_genre_name` and `query_genre_name` directly, so that the alias logic is explicitly exercised rather than covered incidentally through `list_genres`.
8.  As a developer onboarding to the codebase, I want the `jellyfin_media_item` module name and the `MediaItem` glossary entry to agree, so that I can navigate from the domain concept to the code and back.
9.  As a developer reading the directory listing of `jellyswipe/`, I want to see `jellyfin_media_item.py` as a distinct file, so that the seam between "what a MediaItem is" and "how we fetch one" is visible at the import level.
10. As a developer reviewing a PR that changes how movie duration is displayed, I want the diff to touch only `jellyfin_media_item.py` and its tests, so that the scope of the change is self-evident.
11. As a developer reviewing a PR that changes Jellyfin query parameters, I want the diff to touch only `jellyfin_library.py`, so that transformation and transport changes are not mixed.
12. As a future maintainer adding TV show-specific card fields, I want `series_to_media_item` to be a distinct named function in a focused module, so that the movie and TV paths are explicitly separated and individually testable.

## Implementation Decisions

### New module: `jellyfin_media_item`

A new module is created containing only pure functions and constants. It has no mutable state and no imports from any HTTP, auth, or database library.

**Public functions:**

- `movie_to_media_item(it: dict) -> dict` — transforms a raw Jellyfin Movie item response into a MediaItem dict. Replaces the private `_item_to_card` method on `JellyfinLibraryProvider`. Reads `Id`, `Name`, `Overview`, `RunTimeTicks`, `CommunityRating`, `CriticRating`, `ProductionYear` from the raw item; produces `id`, `title`, `summary`, `thumb`, `rating`, `duration`, `year`, `media_type`.
- `series_to_media_item(it: dict) -> dict` — transforms a raw Jellyfin Series item into a MediaItem dict. Replaces the private `_series_to_card` method. Reads `Id`, `Name`, `Overview`, `ProductionYear`, `ChildCount`; produces `id`, `title`, `summary`, `thumb`, `year`, `media_type`, `season_count`.
- `display_genre_name(name: str) -> str` — applies the genre alias table outbound: translates Jellyfin canonical names to display names (e.g. "Science Fiction" → "Sci-Fi"). Used by `list_genres` before returning genre names to the caller.
- `query_genre_name(name: str) -> str` — applies the genre alias table inbound: translates display names back to Jellyfin query parameter values (e.g. "Sci-Fi" → "Science Fiction"). Used by `fetch_deck` and `_fetch_items_for_library` before passing genre filter to the API.

**Private helpers (module-internal):**

- `_format_runtime(seconds: int) -> str` — formats a duration in seconds as a human-readable string (e.g. "1h 45m"). Already a module-level function in `jellyfin_library.py`; moves unchanged.
- `GENRE_ALIASES: dict[str, str]` — the canonical alias table mapping Jellyfin names to display names. `display_genre_name` and `query_genre_name` are both derived from this single constant.

### Changes to `JellyfinLibraryProvider`

- Remove `_item_to_card` method; call `movie_to_media_item` at the call site in `fetch_deck`.
- Remove `_series_to_card` method; call `series_to_media_item` at the call site in `fetch_deck`.
- Remove `_format_runtime` module-level function.
- Replace the three inline genre alias one-liners (in `list_genres`, `fetch_deck`, `_fetch_items_for_library`) with calls to `display_genre_name` and `query_genre_name` respectively.
- No other changes to `JellyfinLibraryProvider`. Query orchestration, HTTP transport, auth state, and caching are untouched.

### No interface changes

The public interface of `JellyfinLibraryProvider` is unchanged. `fetch_deck`, `list_genres`, and all other public methods keep their current signatures and return shapes. This is a pure internal refactor — no callers are affected.

### CONTEXT.md

The `MediaItem`, `Deck`, and `Genre alias` terms have been added to `CONTEXT.md` under a new "Library & Deck" section during the architecture session that produced this PRD. No further glossary changes are needed.

## Testing Decisions

### What makes a good test

Tests should exercise the external behaviour of the module under test through its public interface. A test that breaks because an internal helper was renamed or inlined is a bad test. For this PRD specifically: tests for `movie_to_media_item` should verify the output dict shape given known input dicts; they should not care whether `_format_runtime` is a separate function or an inline expression.

### New test file: `test_jellyfin_media_item`

A new test file is created alongside the existing test suite. It tests all public functions in `jellyfin_media_item` directly, with plain dict inputs and no HTTP mocking or provider instantiation. Coverage targets:

- `movie_to_media_item` with a fully-populated item dict — verify every output field.
- `movie_to_media_item` with missing optional fields (no rating, no runtime, no year) — verify graceful defaults.
- `series_to_media_item` with a fully-populated series dict — verify `media_type`, `season_count`.
- `series_to_media_item` with missing `ChildCount` — verify `season_count` is `None`, not an error.
- `display_genre_name` with a name that has an alias — verify the display form is returned.
- `display_genre_name` with a name that has no alias — verify the name is returned unchanged.
- `query_genre_name` with a display name that has an alias — verify the Jellyfin query form is returned.
- `query_genre_name` with a name that has no alias — verify the name is returned unchanged.
- Round-trip: `query_genre_name(display_genre_name(name)) == name` for all aliased names.

### Existing test suite

`test_jellyfin_library.py` tests that exercise `fetch_deck` and `list_genres` at the provider level require no changes. The transformation functions are called internally; the provider's output shape is unchanged. If any existing test directly references `_item_to_card` or `_series_to_card` as private methods, those references are updated to use the new public module-level function names.

### Prior art

- `test_jellyfin_library.py` for provider-level mocking patterns (reference for how existing deck tests are structured).
- `test_repositories.py` for examples of pure-function and data-contract testing style in this codebase.

## Out of Scope

- **HTTP transport hardening.** `_api()`, `fetch_library_image()`, and retry logic in `JellyfinLibraryProvider` are untouched. Timeout and error-handling consistency is a separate concern noted in PRD 007.
- **Provider cache TTL / invalidation.** `_genre_cache`, `_cached_user_id`, and `_cached_library_ids` have no TTL; that is a known issue but is not addressed here.
- **Query orchestration changes.** `fetch_deck`, `list_genres`, `_fetch_items_for_library`, and `_library_ids_for_type` all remain in `JellyfinLibraryProvider`. This PRD does not move query logic.
- **Provider singleton lifecycle.** The `get_provider` dependency and `reset_provider_singleton` in `dependencies.py` are unchanged.
- **Image proxy separation.** `fetch_library_image` and `_JF_IMAGE_PATH` remain in `JellyfinLibraryProvider`. The regex deduplication between the proxy router and the provider is addressed in PRD 007, not here.
- **Per-user operations.** `add_to_user_favorites`, `resolve_user_id_from_token`, and `user_auth_header` remain in `JellyfinLibraryProvider`.
- **Frontend changes.** The HTML/JS client is untouched. MediaItem field names (`id`, `title`, `summary`, `thumb`, `rating`, `duration`, `year`, `media_type`) must be preserved exactly — they are the API contract with the frontend.
- **API contract changes.** All route paths, response shapes, and HTTP status codes are unchanged.

## Further Notes

- **This change is a pure internal refactor.** No user-visible behaviour changes. The git diff will show: one new file (`jellyfin_media_item.py`), one new test file (`test_jellyfin_media_item.py`), and a net reduction in `jellyfin_library.py` of approximately 40–50 lines. The `CONTEXT.md` update is already committed.
- **Relationship to PRD 007 (Shallow Module Cleanup).** PRD 007 removes the duplicate image-path regex between the proxy router and the provider. This PRD is independent and can be landed before or after PRD 007.
- **Relationship to Architecture Deepening (candidate 1).** The architecture review that produced this PRD also identified deeper splits of `JellyfinLibraryProvider` (HTTP transport, auth, query orchestration). This extraction is the first, smallest, and most clearly bounded step. The deeper splits remain as future candidates and are not blocked or prejudiced by this work.
- `MediaItem` **is not a typed class.** The output of `movie_to_media_item` and `series_to_media_item` is a plain `dict`, matching the existing contract. Introducing a `MediaItem` dataclass or TypedDict is out of scope and would require frontend-facing schema changes to validate against.
