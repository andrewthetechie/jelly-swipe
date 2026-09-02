import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import React, { useEffect, useState } from "react";
import { RoomContextProvider, useRoomSetterContext, useRoomStateContext } from "../RoomContextProvider";
import * as roomApi from "../roomApi";
import * as roomSessionModule from "../RoomSessionProvider";
import type { RoomSessionContextType } from "../RoomSessionProvider";
import type { CardDeck, MatchItem } from "../types";
import { EMPTY_MATCH_ITEM } from "../roomSession";

type RoomStateSeedOverrides = {
  currentRoomCode?: string | null;
  movies?: boolean;
  tvShows?: boolean;
  isSoloMode?: boolean;
  userInputCode?: string;
}

type RoomSessionTestOverrides = {
  cardDeck?: CardDeck;
  swipeHistory?: CardDeck;
  matchFound?: boolean;
  matchItem?: MatchItem;
  roomReady?: boolean;
  genre?: string;
  hideWatched?: boolean;
  lastError?: string | null;
}

type RoomTestOverrides = RoomStateSeedOverrides & RoomSessionTestOverrides

export type RenderWithRoomResult = ReturnType<typeof render>

export type RenderWithRoomStatefulResult = ReturnType<typeof render>

const RoomSessionTestContext = React.createContext<RoomSessionContextType | undefined>(undefined)

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

function installRoomSessionHookMock(): void {
  vi.spyOn(roomSessionModule, "useRoomSession").mockImplementation(() => {
    const value = React.useContext(RoomSessionTestContext)
    if (!value) {
      throw new Error("useRoomSession must be used within a RoomSessionProvider")
    }
    return value
  })
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

function RoomSessionTestProvider({
  children,
  overrides,
  seededDeck,
}: {
  children: React.ReactNode;
  overrides: RoomTestOverrides;
  seededDeck: CardDeck;
}) {
  const { currentRoomCode } = useRoomStateContext()
  const { setCurrentRoomCode } = useRoomSetterContext()
  const [state, setState] = useState({
    cardDeck: seededDeck,
    swipeHistory: overrides.swipeHistory ?? ([] as CardDeck),
    matchFound: overrides.matchFound ?? false,
    matchItem: overrides.matchItem ?? EMPTY_MATCH_ITEM,
    roomReady: overrides.roomReady ?? false,
    genre: overrides.genre ?? "All",
    hideWatched: overrides.hideWatched ?? false,
    lastError: overrides.lastError ?? null,
  })

  useEffect(() => {
    if (!overrides.roomReady || !currentRoomCode || seededDeck.length > 0) {
      return
    }
    roomApi.fetchDeck(currentRoomCode)
      .then((deck) => {
        setState((prev) => ({ ...prev, cardDeck: deck, swipeHistory: [] }))
      })
      .catch((err) => {
        console.error("Error fetching card deck:", err)
      })
  }, [currentRoomCode, seededDeck])

  const swipe = async (
    card: { mediaId: string },
    direction: "left" | "right",
  ) => {
    if (!currentRoomCode) {
      console.error("Cannot send swipe without currentRoomCode")
      return
    }
    try {
      await roomApi.postSwipe(currentRoomCode, card.mediaId, direction)
      setState((prev) => ({
        ...prev,
        cardDeck: prev.cardDeck.slice(1),
        swipeHistory: [...prev.swipeHistory, card as CardDeck[number]],
        lastError: null,
      }))
    } catch (err) {
      console.error("Error POSTing swipe", err)
      setState((prev) => ({ ...prev, lastError: String(err) }))
    }
  }

  const undo = async () => {
    const lastSwipe = state.swipeHistory.at(-1)
    if (!lastSwipe) {
      console.error("Cannot undo without swipe history")
      return
    }
    if (!currentRoomCode) {
      console.error("Cannot send swipe without currentRoomCode")
      return
    }
    try {
      await roomApi.undoSwipe(currentRoomCode, lastSwipe.mediaId)
      setState((prev) => ({
        ...prev,
        cardDeck: [lastSwipe, ...prev.cardDeck],
        swipeHistory: prev.swipeHistory.slice(0, -1),
        lastError: null,
      }))
    } catch (err) {
      console.error("Error undoing swipe", err)
      setState((prev) => ({ ...prev, lastError: String(err) }))
    }
  }

  const selectGenre = (genre: string) => {
    setState((prev) => ({ ...prev, genre }))
  }

  const confirmGenre = async () => {
    if (!currentRoomCode) {
      console.error("Cannot change genre without currentRoomCode")
      return
    }
    try {
      const result = await roomApi.setGenreChoice(currentRoomCode, state.genre)
      setState((prev) => ({
        ...prev,
        cardDeck: result.deck,
        swipeHistory: [],
        lastError: null,
      }))
    } catch (err) {
      console.error("Error changing genre", err)
      setState((prev) => ({ ...prev, lastError: String(err) }))
    }
  }

  const toggleHideWatched = async () => {
    if (!currentRoomCode) {
      console.error("Cannot toggle watched filter without currentRoomCode")
      return
    }
    const next = !state.hideWatched
    try {
      const result = await roomApi.setWatchedFilter(currentRoomCode, next)
      setState((prev) => ({
        ...prev,
        cardDeck: result.deck,
        swipeHistory: [],
        hideWatched: next,
        lastError: null,
      }))
    } catch (err) {
      console.error("Error toggling watched filter", err)
      setState((prev) => ({ ...prev, lastError: String(err) }))
    }
  }

  const dismissMatch = () => {
    setState((prev) => ({ ...prev, matchFound: false }))
  }

  const endSession = async () => {
    if (!currentRoomCode) {
      console.error("Cannot end session without currentRoomCode")
      return
    }
    try {
      await roomApi.quitRoom(currentRoomCode)
      setState((prev) => ({
        ...prev,
        roomReady: false,
        hideWatched: false,
        cardDeck: [],
        swipeHistory: [],
        matchFound: false,
        matchItem: EMPTY_MATCH_ITEM,
      }))
      setCurrentRoomCode(null)
    } catch (err) {
      console.error("Error quitting room", err)
      setState((prev) => ({ ...prev, lastError: String(err) }))
    }
  }

  const value: RoomSessionContextType = {
    state,
    swipe,
    undo,
    selectGenre,
    confirmGenre,
    toggleHideWatched,
    dismissMatch,
    endSession,
  }

  return (
    <RoomSessionTestContext.Provider value={value}>
      {children}
    </RoomSessionTestContext.Provider>
  )
}

export function renderWithRoom(
  ui: ReactElement,
  overrides: RoomTestOverrides = {},
): RenderWithRoomResult {
  const seededDeck = overrides.cardDeck ?? extractDeckFromUi(ui)
  installRoomSessionHookMock()

  return render(
    <RoomContextProvider>
      <RoomStateSeeder
        currentRoomCode={overrides.currentRoomCode}
        movies={overrides.movies}
        tvShows={overrides.tvShows}
        isSoloMode={overrides.isSoloMode}
        userInputCode={overrides.userInputCode}
      >
        <RoomSessionTestProvider overrides={overrides} seededDeck={seededDeck}>
          <RoomStateProbe />
          {ui}
        </RoomSessionTestProvider>
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
