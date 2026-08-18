# ADR 0003: Deck domain module at the repository seam

## Status

Accepted (issue #294).

## Context

A room's swipe deck is stored across two room columns — `movie_data` (the
ordered card list, JSON) and `deck_position` (a per-user cursor map, JSON).
Before this change, parsing and re-serializing those two blobs was re-implemented
in four places with divergent error tolerance:

- `deck_pipeline.build_deck` wrote them via `set_filters_and_deck`.
- `room_lifecycle` (create / join / `get_deck`) had its own tolerant `_cursor_from_deck_json` parser and re-mapped `id` → `media_id`.
- `session_match_mutation` had `_card_from_deck` and, worst of all, called a bare `json.loads(room.deck_position_json)` during the swipe transaction — so a corrupt cursor blob **crashed the swipe**.
- `RoomRepository` exposed the raw JSON strings on `RoomRecord`, leaking parser knowledge into every consumer.

Because each parser tolerated corruption slightly differently, behavior drifted:
`get_deck` defaulted `media_type` to `"movie"`, while `build_deck`'s persist-time
API conversion did not.

## Decision

Introduce a single **`Deck`** domain module at the repository seam:

- A new `jellyswipe/domain/deck.py` holds an immutable (frozen) `Deck` dataclass
  (`cards` + `cursors`) owning parse, cursor advance, participant add, cursor
  reset, page slicing, card lookup, API-shape conversion, and serialization.
- `RoomRepository` takes and returns `Deck` objects for the deck columns —
  `RoomRecord.deck` replaces the raw `movie_data_json` / `deck_position_json`
  fields, and write methods (`create`, `set_deck_position`,
  `set_filters_and_deck`) accept a `Deck` and serialize internally.
- `deck_pipeline`, `room_lifecycle`, and `session_match_mutation` all consume
  the one `Deck` interface; the three independent parsers and the duplicated
  `id` ↔ `media_id` remapping are deleted.

### Placement (dependency direction)

`Deck` lives in a new `jellyswipe/domain/` package rather than `services/`
because `RoomRepository` must import it. Putting it in `services/` would invert
the existing layering (repositories → services), which the codebase does not do.
`domain/` sits below both `services` and `repositories`, so both can depend on it
with no cycle.

### Cards stay dicts

Cards remain `dict[str, Any]` (a `Card` type alias) rather than becoming a typed
class. Every consumer already does `card.get(...)`, so a typed `Card` would force
conversion churn with no behavioral gain. The deepening win here is the
parse/serialize/cursor seam, not card typing.

## Consequences

- **One tolerant error policy.** `Deck.parse` degrades corrupt/non-dict/non-list
  input to an empty deck / empty cursor map and logs a single warning. The swipe
  path now recovers instead of raising on a corrupt `deck_position` blob, and the
  recovered cursor map is persisted, overwriting the corrupt value (self-healing).
- **One `id` → `media_id` mapping.** `Deck.api_cards()` is the single site; both
  `get_deck` pagination and `build_deck`'s persist-time return use it. The
  persisted-return path for `set_genre` / `set_watched_filter` now also defaults
  `media_type` to `"movie"` (an additive public-payload change; the frontend
  ignores unknown keys).
- **Dead surface removed.** `set_genre_and_deck` and `fetch_movie_data` were only
  exercised by tests, and `deck_order_json` was read by nothing. They were removed
  with this change; the `deck_order` column is untouched (no migration).
- **Cursors reset on rebuild** (genre / watched-filter change) is preserved via
  `Deck.from_cards(...)` producing an empty cursor map, matching prior behavior.
