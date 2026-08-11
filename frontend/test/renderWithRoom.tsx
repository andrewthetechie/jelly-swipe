import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import React, { useState } from "react";
import { RoomStateContext, RoomSetterContext } from "../RoomContextProvider";
import type { RoomStateContextType, RoomSetterContextType } from "../RoomContextProvider";

type RoomTestContext = RoomStateContextType & RoomSetterContextType

function makeDefaultStateCtx(): RoomStateContextType {
  return {
    currentRoomCode: null,
    roomReady: false,
    movies: true,
    tvShows: false,
    isSoloMode: false,
    userInputCode: "",
    genre: "All",
    hideWatched: false,
  } as unknown as RoomStateContextType;
}

function makeDefaultSetterCtx(): RoomSetterContextType {
  return {
    setCurrentRoomCode: vi.fn(),
    setRoomReady: vi.fn(),
    setMovies: vi.fn(),
    setTvShows: vi.fn(),
    setIsSoloMode: vi.fn(),
    setUserInputCode: vi.fn(),
    setGenre: vi.fn(),
    setHideWatched: vi.fn(),
  } as unknown as RoomSetterContextType;
}

export interface RenderWithRoomResult extends ReturnType<typeof render> {
  ctx: RoomTestContext;
}

export type RenderWithRoomStatefulResult = ReturnType<typeof render>

// Spy-oriented helper: use when you need to assert setter calls via returned ctx.
export function renderWithRoom(
  ui: ReactElement,
  overrides: Partial<RoomTestContext> = {},
): RenderWithRoomResult {

  const defaultState = makeDefaultStateCtx()
  const defaultSetters = makeDefaultSetterCtx()

  const stateCtx: RoomStateContextType = {
    currentRoomCode: overrides.currentRoomCode ?? defaultState.currentRoomCode,
    roomReady: overrides.roomReady ?? defaultState.roomReady,
    movies: overrides.movies ?? defaultState.movies,
    tvShows: overrides.tvShows ?? defaultState.tvShows,
    isSoloMode: overrides.isSoloMode ?? defaultState.isSoloMode,
    userInputCode: overrides.userInputCode ?? defaultState.userInputCode,
    genre: overrides.genre ?? defaultState.genre,
    hideWatched: overrides.hideWatched ?? defaultState.hideWatched,
  }

  const setterCtx: RoomSetterContextType = {
    setCurrentRoomCode: overrides.setCurrentRoomCode ?? defaultSetters.setCurrentRoomCode,
    setRoomReady: overrides.setRoomReady ?? defaultSetters.setRoomReady,
    setMovies: overrides.setMovies ?? defaultSetters.setMovies,
    setTvShows: overrides.setTvShows ?? defaultSetters.setTvShows,
    setIsSoloMode: overrides.setIsSoloMode ?? defaultSetters.setIsSoloMode,
    setUserInputCode: overrides.setUserInputCode ?? defaultSetters.setUserInputCode,
    setGenre: overrides.setGenre ?? defaultSetters.setGenre,
    setHideWatched: overrides.setHideWatched ?? defaultSetters.setHideWatched,
  }

  const result = render(
    <RoomSetterContext.Provider value={setterCtx}>
      <RoomStateContext.Provider value={stateCtx}>
        {ui}
      </RoomStateContext.Provider>
    </RoomSetterContext.Provider>
  );
  return { ...result, ctx: { ...stateCtx, ...setterCtx } };
}

// Stateful DOM helper: use for UI/state transition assertions; intentionally does not return ctx.
export function renderWithRoomStateful(
  ui: ReactElement,
  overrides: Partial<RoomTestContext> = {},
): RenderWithRoomStatefulResult {
  function Provider({ children }: { children: React.ReactNode }) {
    const [movies, setMoviesState] = useState<boolean>(overrides.movies ?? true)
    const [tvShows, setTvShowsState] = useState<boolean>(overrides.tvShows ?? false)
    const [isSoloMode, setIsSoloModeState] = useState<boolean>(overrides.isSoloMode ?? false)
    const [roomReady, setRoomReadyState] = useState<boolean>(overrides.roomReady ?? false)
    const [currentRoomCode, setCurrentRoomCodeState] = useState<string | null>(
      overrides.currentRoomCode ?? null,
    )
    const [userInputCode, setUserInputCodeState] = useState<string>(
      overrides.userInputCode ?? "",
    )
    const [genre, setGenreState] = useState<string>(
      overrides.genre ?? "All",
    )
    const [hideWatched, setHideWatchedState] = useState<boolean>(overrides.hideWatched ?? false)

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
    const setRoomReadySpy = overrides.setRoomReady ?? vi.fn()
    const setMoviesSpy = overrides.setMovies ?? vi.fn()
    const setTvShowsSpy = overrides.setTvShows ?? vi.fn()
    const setIsSoloModeSpy = overrides.setIsSoloMode ?? vi.fn()
    const setUserInputCodeSpy = overrides.setUserInputCode ?? vi.fn()
    const setGenreSpy = overrides.setGenre ?? vi.fn()
    const setHideWatchedSpy = overrides.setHideWatched ?? vi.fn()

    const stateCtx: RoomStateContextType = {
      currentRoomCode,
      roomReady,
      movies,
      tvShows,
      isSoloMode,
      userInputCode,
      genre,
      hideWatched,
  }

  const setterCtx: RoomSetterContextType = {
      setCurrentRoomCode: vi.fn((action: React.SetStateAction<string | null>) => {
        setCurrentRoomCodeSpy(action)
        applySetStateAction(action, setCurrentRoomCodeState)
      }),
      setRoomReady: vi.fn((action: React.SetStateAction<boolean>) => {
        setRoomReadySpy(action)
        applySetStateAction(action, setRoomReadyState)
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
      setGenre: vi.fn((action: React.SetStateAction<string>) => {
        setGenreSpy(action)
        applySetStateAction(action, setGenreState)
      }),
      setHideWatched: vi.fn((action: React.SetStateAction<boolean>) => {
        setHideWatchedSpy(action)
        applySetStateAction(action, setHideWatchedState)
      }),
    }

    return (
      <RoomSetterContext.Provider value={setterCtx}>
        <RoomStateContext.Provider value={stateCtx}>
          {children}
        </RoomStateContext.Provider>
      </RoomSetterContext.Provider>
    )
  }

  const result = render(<Provider>{ui}</Provider>);

  return { ...result }
}
