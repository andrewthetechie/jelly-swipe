import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import React, { useEffect, useState } from "react";
import { RoomStateContext, RoomSetterContext } from "../RoomContextProvider";
import type { RoomStateContextType, RoomSetterContextType } from "../RoomContextProvider";
import { useRoomSetterContext, useRoomStateContext } from "../RoomContextProvider";
import * as roomApi from "../roomApi";
import * as roomSessionModule from "../RoomSessionProvider";
import type { RoomSessionContextType } from "../RoomSessionProvider";
import type { CardDeck, MatchItem } from "../types";
import { EMPTY_MATCH_ITEM } from "../roomSession";

type RoomTestContext = RoomStateContextType & RoomSetterContextType

type RoomSessionTestOverrides = {
  cardDeck?: CardDeck;
  swipeHistory?: CardDeck;
  matchFound?: boolean;
  matchItem?: MatchItem;
  roomReady?: boolean;
  genre?: string;
  hideWatched?: boolean;
  pendingDeckRefresh?: "genre" | "hide_watched" | null;
  lastError?: string | null;
}

type RoomTestOverrides = Partial<RoomTestContext> & RoomSessionTestOverrides

function makeDefaultStateCtx(): RoomStateContextType {
  return {
    currentRoomCode: null,
    movies: true,
    tvShows: false,
    isSoloMode: false,
    userInputCode: "",
  };
}

function makeDefaultSetterCtx(): RoomSetterContextType {
  return {
    setCurrentRoomCode: vi.fn(),
    setMovies: vi.fn(),
    setTvShows: vi.fn(),
    setIsSoloMode: vi.fn(),
    setUserInputCode: vi.fn(),
  };
}

export interface RenderWithRoomResult extends ReturnType<typeof render> {
  ctx: RoomTestContext;
}

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
    pendingDeckRefresh: overrides.pendingDeckRefresh ?? null,
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
    card: { media_id: string },
    direction: "left" | "right",
  ) => {
    if (!currentRoomCode) {
      console.error("Cannot send swipe without currentRoomCode")
      return
    }
    try {
      await roomApi.postSwipe(currentRoomCode, card.media_id, direction)
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
      await roomApi.undoSwipe(currentRoomCode, lastSwipe.media_id)
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
      const deck = await roomApi.setGenreChoice(currentRoomCode, state.genre)
      setState((prev) => ({
        ...prev,
        cardDeck: deck,
        swipeHistory: [],
        pendingDeckRefresh: "genre",
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
      const deck = await roomApi.setWatchedFilter(currentRoomCode, next)
      setState((prev) => ({
        ...prev,
        cardDeck: deck,
        swipeHistory: [],
        hideWatched: next,
        pendingDeckRefresh: "hide_watched",
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
        pendingDeckRefresh: null,
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

// Spy-oriented helper: use when you need to assert setter calls via returned ctx.
export function renderWithRoom(
  ui: ReactElement,
  overrides: RoomTestOverrides = {},
): RenderWithRoomResult {
  const seededDeck = overrides.cardDeck ?? extractDeckFromUi(ui)
  installRoomSessionHookMock()

  const defaultState = makeDefaultStateCtx()
  const defaultSetters = makeDefaultSetterCtx()

  const stateCtx: RoomStateContextType = {
    currentRoomCode: overrides.currentRoomCode ?? defaultState.currentRoomCode,
    movies: overrides.movies ?? defaultState.movies,
    tvShows: overrides.tvShows ?? defaultState.tvShows,
    isSoloMode: overrides.isSoloMode ?? defaultState.isSoloMode,
    userInputCode: overrides.userInputCode ?? defaultState.userInputCode,
  }

  const setterCtx: RoomSetterContextType = {
    setCurrentRoomCode: overrides.setCurrentRoomCode ?? defaultSetters.setCurrentRoomCode,
    setMovies: overrides.setMovies ?? defaultSetters.setMovies,
    setTvShows: overrides.setTvShows ?? defaultSetters.setTvShows,
    setIsSoloMode: overrides.setIsSoloMode ?? defaultSetters.setIsSoloMode,
    setUserInputCode: overrides.setUserInputCode ?? defaultSetters.setUserInputCode,
  }

  const result = render(
    <RoomSetterContext.Provider value={setterCtx}>
      <RoomStateContext.Provider value={stateCtx}>
        <RoomSessionTestProvider overrides={overrides} seededDeck={seededDeck}>
          {ui}
        </RoomSessionTestProvider>
      </RoomStateContext.Provider>
    </RoomSetterContext.Provider>
  );
  return { ...result, ctx: { ...stateCtx, ...setterCtx } };
}

// Stateful DOM helper: use for UI/state transition assertions; intentionally does not return ctx.
export function renderWithRoomStateful(
  ui: ReactElement,
  overrides: RoomTestOverrides = {},
): RenderWithRoomStatefulResult {
  const seededDeck = overrides.cardDeck ?? extractDeckFromUi(ui)
  installRoomSessionHookMock()

  function Provider({ children }: { children: React.ReactNode }) {
    const [movies, setMoviesState] = useState<boolean>(overrides.movies ?? true)
    const [tvShows, setTvShowsState] = useState<boolean>(overrides.tvShows ?? false)
    const [isSoloMode, setIsSoloModeState] = useState<boolean>(overrides.isSoloMode ?? false)
    const [currentRoomCode, setCurrentRoomCodeState] = useState<string | null>(
      overrides.currentRoomCode ?? null,
    )
    const [userInputCode, setUserInputCodeState] = useState<string>(
      overrides.userInputCode ?? "",
    )

    const applySetStateAction = <T,>(
      action: React.SetStateAction<T>,
      setState: React.Dispatch<React.SetStateAction<T>>,
    ) => {
      setState((prev) =>
        typeof action === "function"
          ? (action as (prev: T) => T)(prev)
          : action,
      )
    }

    const setCurrentRoomCodeSpy = overrides.setCurrentRoomCode ?? vi.fn()
    const setMoviesSpy = overrides.setMovies ?? vi.fn()
    const setTvShowsSpy = overrides.setTvShows ?? vi.fn()
    const setIsSoloModeSpy = overrides.setIsSoloMode ?? vi.fn()
    const setUserInputCodeSpy = overrides.setUserInputCode ?? vi.fn()

    const stateCtx: RoomStateContextType = {
      currentRoomCode,
      movies,
      tvShows,
      isSoloMode,
      userInputCode,
  }

  const setterCtx: RoomSetterContextType = {
      setCurrentRoomCode: vi.fn((action: React.SetStateAction<string | null>) => {
        setCurrentRoomCodeSpy(action)
        applySetStateAction(action, setCurrentRoomCodeState)
      }),
      setMovies: vi.fn((action: React.SetStateAction<boolean>) => {
        setMoviesSpy(action)
        applySetStateAction(action, setMoviesState)
      }),
      setTvShows: vi.fn((action: React.SetStateAction<boolean>) => {
        setTvShowsSpy(action)
        applySetStateAction(action, setTvShowsState)
      }),
      setIsSoloMode: vi.fn((action: React.SetStateAction<boolean>) => {
        setIsSoloModeSpy(action)
        applySetStateAction(action, setIsSoloModeState)
      }),
      setUserInputCode: vi.fn((action: React.SetStateAction<string>) => {
        setUserInputCodeSpy(action)
        applySetStateAction(action, setUserInputCodeState)
      }),
    }

    return (
      <RoomSetterContext.Provider value={setterCtx}>
        <RoomStateContext.Provider value={stateCtx}>
          <RoomSessionTestProvider overrides={overrides} seededDeck={seededDeck}>
            {children}
          </RoomSessionTestProvider>
        </RoomStateContext.Provider>
      </RoomSetterContext.Provider>
    )
  }

  const result = render(<Provider>{ui}</Provider>);

  return { ...result }
}
