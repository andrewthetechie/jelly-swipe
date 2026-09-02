# Issue 273 — SSE Mutation Event-ID Correlation

Eliminate the local SSE echo race on genre/hide-watched mutations by correlating
mutation identity instead of using value/timing heuristics. Backend and frontend
land as **two separate commits** in **one PR**. No backwards-compatibility
constraint (the POST response contract changes).

## Decisions (agreed via grilling)

- Backend POST envelopes: `{ "deck": [...], "mutation_event_id": <int>, "mutation_type": "genre_changed" | "hide_watched_changed" }`.
- Frontend keeps the **deck-from-POST** path; the SSE echo only updates mirrored
  state and its refetch is suppressed for local mutations.
- Suppression is deterministic, using an **optimistic in-flight flag** (POST sent)
  **plus** a **registered event-ID set** (POST completed). No timer, no
  `pendingDeckRefresh`, no value-equality guard.
- Registered IDs are **retained across SSE reconnects** (so a replayed own-echo is
  still suppressed), bounded LRU (~50), cleared on room leave / `session_closed`.
  The in-flight flag is cleared on reconnect and on POST completion (success or fail).
- Scope is **only** `POST /room/{code}/genre` and `POST /room/{code}/watched-filter`
  and their `genre_changed` / `hide_watched_changed` echoes. The SSE **emission**
  schema is unchanged; no other event/mutation flows are touched.
- **Commit structure (red interim allowed)**: backend commit may leave the frontend
  failing until the frontend commit lands; the PR-level CI is the gate.

## Domain vocabulary (already added to CONTEXT.md)

- **event identity** — the monotonic `event_id` that tells two same-`event_type`
  events apart.
- **mutation echo** — an SSE event caused by the client's own mutation.
- **remote mutation** — an SSE event caused by another participant; only these
  trigger a deck refetch.

---

## Commit 1 — Backend (contract + tests)

**Files:** `jellyswipe/schemas/rooms.py`, `jellyswipe/schemas/common.py` (reuse
`CardItem`), `jellyswipe/services/room_lifecycle.py`, `jellyswipe/routers/rooms.py`,
`tests/test_routes_room.py`.

1. Add a response schema (in `schemas/rooms.py`), e.g. `MutationChangeResponse`:
   `deck: list[CardItem]`, `mutation_event_id: int`, `mutation_type: str`.
2. `RoomLifecycle.set_genre` / `set_watched_filter`: capture the return value of
   `uow.session_events.append(...)` (already returns the new `event_id`; today it is
   discarded) and return it alongside the deck. Return a small result object (or
   `(deck, mutation_event_id)`), since these methods are only called by the two
   routes.
3. `rooms.py` `set_genre` / `set_watched_filter_route`: set `response_model=
   MutationChangeResponse` and compose the response from the service result
   (`deck`, `mutation_event_id`, and the literal `mutation_type` for the endpoint).
   Keep `wake_on_commit(code)` and the existing `EmptyDeckError` → 400/422 paths
   unchanged (failure appends no event and returns no id).
4. Tests (`tests/test_routes_room.py`): update the two success-path tests to assert
   the new envelope (`deck` array + `mutation_event_id` int + `mutation_type`), and
   keep empty-deck 400/422 assertions. Add a test that `mutation_event_id` is a
   *new* strictly-increasing id across two successive mutations.

**Verification:** `uv run pytest tests/test_routes_room.py -v` and `uv run ruff check .`.

---

## Commit 2 — Frontend (consumers + race tests)

**Files:** `frontend/roomApi.ts`, `frontend/roomSession.ts`, `frontend/RoomSessionProvider.tsx`,
`frontend/types.ts`, `frontend/roomSession.test.ts`, `frontend/SwipePage.test.tsx`
(or a focused provider test), `frontend/roomApi.test.ts`.

1. `types.ts` / `roomApi.ts`: `setGenreChoice` / `setWatchedFilter` return
   `{ deck: CardDeck, mutationEventId: number, mutationType: string }` parsed from
   the new envelope.
2. `roomSession.ts`:
   - Remove `pendingDeckRefresh` from `RoomSessionState`, its actions
     (`GENRE_COMMAND_SUCCEEDED`, `HIDE_WATCHED_COMMAND_SUCCEEDED`), and the
     `SSE_GENRE_CHANGED` / `SSE_HIDE_WATCHED_CHANGED` clearing logic.
   - Those command-success actions carry `mutationEventId`.
   - Remove the value-equality guard from `shouldRefreshDeck`; its suppression role
     is replaced by the provider's in-flight/ID checks. It may be removed or kept as
     a thin "does this event change anything worth refreshing" for remote events.
   - The SSE `genre_changed` / `hide_watched_changed` actions still update
     `genre` / `hideWatched` mirrored state (unchanged).
3. `RoomSessionProvider.tsx`: host the suppression state in a ref:
   - `inFlight: Set<"genre" | "hide_watched">` — add on POST send, remove on POST
     completion (success or failure).
   - `ignoredEventIds: Set<number>` — add the returned `mutationEventId` on success,
     bounded LRU (~50), **retained across reconnects**.
   - In the SSE handler for `genre_changed` / `hide_watched_changed`: an event is
     *local* if `inFlight.has(type) || ignoredEventIds.has(event_id)`. If local,
     skip the deck refetch (and consume the id); otherwise refetch via
     `roomApi.fetchDeck`. Always dispatch the mirrored-state action afterward.
   - Clear `inFlight` on reconnect / `session_reset`; clear both collections on
     `session_closed` / room leave.
4. Tests — the race/orderings acceptance matrix:
   - **Own echo after POST** → no duplicate deck fetch (ID match suppresses).
   - **Delayed echo / reconnect replay** → still suppressed (ID retained).
   - **Echo before POST (in-flight)** → suppressed, no spurious refetch for
     `hide_watched`, and no stuck suppression: a **subsequent remote** mutation
     still triggers a refetch.
   - **Remote mutation** (unrelated `event_id`, no in-flight) → refetch.
   - **POST failure** → nothing registered, in-flight cleared, no stale suppression.
   - Both local and remote echoes update `genre` / `hideWatched` mirrored state.

**Verification:** `npx vitest run`, `npx tsc --noEmit`, `npm run lint`.

---

## Acceptance boundary

Per issue #273: (1) endpoints return `mutation_event_id`/`mutation_type` + deck;
(2) frontend suppresses only the exact matching local echo; (3) no timer-based
window remains for these flows (also removes the `pendingDeckRefresh` sentinel);
(4) remote participant changes still trigger a deck refresh — including in the
echo-before-POST ordering that previously broke this; (5) race and slow-network
scenarios are covered and pass.

## Out of scope

- SSE protocol/emission redesign (replay, framing, payloads unchanged).
- Match-found, session-*, swipe/undo flows.
- Backwards compatibility shims for the changed POST contract.

## Implementation hygiene (GitNexus / repo conventions)

Before editing, run impact analysis on `RoomLifecycle.set_genre`,
`RoomLifecycle.set_watched_filter`, and `shouldRefreshDeck` (and the routes) and
report blast radius, per AGENTS.md. Use explicit `git add <file>` paths; never
`git add .`. Run change detection before committing to confirm only expected
symbols changed.
