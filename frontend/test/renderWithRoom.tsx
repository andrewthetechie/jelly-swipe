import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import React from "react";
import { RoomContextProvider, useRoomSetterContext, useRoomStateContext } from "../RoomContextProvider";
import { SSEContext } from "../SSEContextProvider";
import * as roomApi from "../roomApi";
import { RoomSessionProvider } from "../RoomSessionProvider";
import type { RoomSessionApi } from "../roomSessionStore";
import type { RoomSessionState } from "../roomSession";
import type { CardDeck, MatchItem } from "../types";
import { EMPTY_MATCH_ITEM } from "../roomSession";

type RoomStateSeedOverrides = {
  currentRoomCode?: string | null;
  movies?: boolean;
  tvShows?: boolean;
  isSoloMode?: boolean;
  userInputCode?: string;
}

// The real RoomSessionProvider resets the session store on mount: joining a
// room dispatches DECK_LOADED (which clears swipeHistory) and leaving/resetting
// dispatches DECK_RESET (which clears cardDeck, swipeHistory, deckError and
// deckLoaded). So `swipeHistory` can never survive the provider's room-code
// lifecycle — it is intentionally not a valid seed and is omitted here. The
// remaining seeds survive only when a `currentRoomCode` is passed: `cardDeck`
// is served by the join fetch and `deckError` models a failed initial load.
type RoomSessionTestOverrides = {
  cardDeck?: CardDeck;
  matchFound?: boolean;
  matchItem?: MatchItem;
  roomReady?: boolean;
  genre?: string;
  hideWatched?: boolean;
  lastError?: string | null;
  deckError?: string | null;
  deckLoaded?: boolean;
}

type RoomTestOverrides = RoomStateSeedOverrides & RoomSessionTestOverrides

export type RenderWithRoomResult = ReturnType<typeof render>

export type RenderWithRoomStatefulResult = ReturnType<typeof render>

function extractDeckFromUi(ui: ReactElement): CardDeck {
  const topLevelDeck = (ui as { props?: { cardDeck?: CardDeck } }).props?.cardDeck
  if (Array.isArray(topLevelDeck)) {
    return topLevelDeck
  }
  const children = (ui as { props?: { children?: unknown } }).props?.children
  if (React.isValidElement(children)) {
    const childDeck = (children as { props?: { cardDeck?: CardDeck } }).props?.cardDeck
    if (Array.isArray(childDeck)) {
      return childDeck
    }
  }
  return []
}

function RoomStateSeeder({
  children,
  currentRoomCode,
  movies,
  tvShows,
  isSoloMode,
  userInputCode,
}: {
  children: React.ReactNode;
  currentRoomCode?: string | null;
  movies?: boolean;
  tvShows?: boolean;
  isSoloMode?: boolean;
  userInputCode?: string;
}) {
  const { setCurrentRoomCode, setMovies, setTvShows, setIsSoloMode, setUserInputCode } = useRoomSetterContext()
  const seededRef = React.useRef(false)
  const [isReady, setIsReady] = React.useState(false)

  React.useLayoutEffect(() => {
    if (seededRef.current) {
      return
    }

    seededRef.current = true

    if (currentRoomCode !== undefined) {
      setCurrentRoomCode(currentRoomCode)
    }
    if (movies !== undefined) {
      setMovies(movies)
    }
    if (tvShows !== undefined) {
      setTvShows(tvShows)
    }
    if (isSoloMode !== undefined) {
      setIsSoloMode(isSoloMode)
    }
    if (userInputCode !== undefined) {
      setUserInputCode(userInputCode)
    }

    setIsReady(true)
  }, [
    currentRoomCode,
    movies,
    tvShows,
    isSoloMode,
    userInputCode,
    setCurrentRoomCode,
    setMovies,
    setTvShows,
    setIsSoloMode,
    setUserInputCode,
  ])

  if (!isReady) {
    return null
  }

  return <>{children}</>
}

function RoomStateProbe() {
  const state = useRoomStateContext()

  return <pre data-testid="room-state" hidden>{JSON.stringify(state)}</pre>
}

/**
 * Build the fake api injected into the real RoomSessionProvider.
 *
 * The provider's store is wired to this object instead of the roomApi module so
 * the ten component suites never hit the network, while still honouring
 * suite-level `vi.mock("./roomApi")` mocks:
 *
 *   - For each session function, if the imported roomApi function is a mock,
 *     delegate to it so the suite stays in control (e.g. SwipePage asserts on
 *     its fetchDeck/postSwipe mocks).
 *   - Otherwise use a safe no-network default (the seeded deck for fetchDeck,
 *     resolved values for the commands). The one exception is quitRoom, which
 *     is forwarded to the real function when present so suites that intercept
 *     fetch via mockFetch (HostWaiting) keep observing the network contract.
 *
 * A seeded `deckError` models a failed *initial* load, so the default fetchDeck
 * rejects once (matching the real provider's always-fetch-on-join policy) when
 * no suite mock overrides it.
 */
function buildFakeApi(seededDeck: CardDeck, seededDeckError: string | null): RoomSessionApi {
  let initialLoadFailed = false

  const imported = (key: keyof RoomSessionApi): unknown =>
    (roomApi as unknown as Record<keyof RoomSessionApi, unknown>)[key]

  const delegateIfMock = <K extends keyof RoomSessionApi>(key: K): RoomSessionApi[K] | undefined => {
    const fn = imported(key)
    if (typeof fn === "function" && vi.isMockFunction(fn)) {
      return fn as unknown as RoomSessionApi[K]
    }
    return undefined
  }

  return {
    fetchDeck: async (roomCode) => {
      const mock = delegateIfMock("fetchDeck")
      if (mock) {
        const deck = await mock(roomCode)
        // A bare vi.fn() with no resolved value yields undefined — treat that as
        // "suite didn't configure the deck" and fall through to the seeded deck.
        if (deck !== undefined) {
          return deck
        }
      }
      if (seededDeckError && !initialLoadFailed) {
        initialLoadFailed = true
        throw new Error("Couldn't load your cards. Check your connection and try again.")
      }
      return seededDeck
    },
    postSwipe: async (roomCode, mediaId, direction) => {
      const mock = delegateIfMock("postSwipe")
      if (mock) return mock(roomCode, mediaId, direction)
      return
    },
    undoSwipe: async (roomCode, mediaId) => {
      const mock = delegateIfMock("undoSwipe")
      if (mock) return mock(roomCode, mediaId)
      return
    },
    setGenreChoice: async (roomCode, genre) => {
      const mock = delegateIfMock("setGenreChoice")
      if (mock) return mock(roomCode, genre)
      return { deck: seededDeck, mutationEventId: 0, mutationType: "genre_changed" as const }
    },
    setWatchedFilter: async (roomCode, hideWatched) => {
      const mock = delegateIfMock("setWatchedFilter")
      if (mock) return mock(roomCode, hideWatched)
      return { deck: seededDeck, mutationEventId: 0, mutationType: "hide_watched_changed" as const }
    },
    quitRoom: async (roomCode) => {
      const mock = delegateIfMock("quitRoom")
      if (mock) return mock(roomCode)
      const real = imported("quitRoom")
      if (typeof real === "function") return real(roomCode)
      return { status: "ok" }
    },
  }
}

export function renderWithRoom(
  ui: ReactElement,
  overrides: RoomTestOverrides = {},
): RenderWithRoomResult {
  const seededDeck = overrides.cardDeck ?? extractDeckFromUi(ui)
  const fakeApi = buildFakeApi(seededDeck, overrides.deckError ?? null)

  const initialState: RoomSessionState = {
    cardDeck: seededDeck,
    swipeHistory: [] as CardDeck,
    matchFound: overrides.matchFound ?? false,
    matchItem: overrides.matchItem ?? EMPTY_MATCH_ITEM,
    roomReady: overrides.roomReady ?? false,
    genre: overrides.genre ?? "All",
    hideWatched: overrides.hideWatched ?? false,
    lastError: overrides.lastError ?? null,
    deckError: overrides.deckError ?? null,
    deckLoaded: overrides.deckLoaded ?? false,
  }

  // A neutral, no-network SSE context value so the real RoomSessionProvider's
  // useSSEContext() is satisfied. Suites that care about SSE supply their own
  // SSEContextProvider inside the tree (e.g. SSEContextProvider.test.tsx).
  const sseValue = { sseData: null, sseError: null, isConnected: false }

  return render(
    <RoomContextProvider>
      <RoomStateSeeder
        currentRoomCode={overrides.currentRoomCode}
        movies={overrides.movies}
        tvShows={overrides.tvShows}
        isSoloMode={overrides.isSoloMode}
        userInputCode={overrides.userInputCode}
      >
        <SSEContext.Provider value={sseValue}>
          <RoomSessionProvider api={fakeApi} initialState={initialState}>
            <RoomStateProbe />
            {ui}
          </RoomSessionProvider>
        </SSEContext.Provider>
      </RoomStateSeeder>
    </RoomContextProvider>
  )
}

export function renderWithRoomStateful(
  ui: ReactElement,
  overrides: RoomTestOverrides = {},
): RenderWithRoomStatefulResult {
  return renderWithRoom(ui, overrides)
}
