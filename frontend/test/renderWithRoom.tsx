// renderWithRoom — the shared helper for rendering any component that needs the
// room context.
//
// Why this exists: the redesign's components call `useRoomContext()`, which
// THROWS if there is no <RoomContext.Provider> above them. So we cannot just
// `render(<Header />)` — we must wrap it in a provider. This helper does that
// with sensible defaults and `vi.fn()` spies for every setter, so a test can:
//   1. preset values (e.g. `{ currentRoomCode: "1234" }`), and
//   2. assert that a component called a setter (e.g. `ctx.setCurrentRoomCode`).
//
// IMPORTANT (the "two RoomContext instances" gotcha): there are TWO separate
// RoomContext objects in this codebase. App.tsx declares and exports one, but
// it is dead/unused. The LIVE one — the object the components actually read —
// is the one created inside RoomContextProvider.tsx. We import THAT one (now
// exported for tests). Wrapping App.tsx's copy would not reach the components
// and they would hit the `useRoomContext` throw. See frontend/README.md.
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import React, { useState } from "react";
import { RoomContext, type RoomContextType } from "../RoomContextProvider";

// Build a default context: plausible starting values plus a vi.fn() spy for
// every setter. Tests can override any field via the second argument.
function makeDefaultCtx(): RoomContextType {
  return {
    currentRoomCode: null,
    setCurrentRoomCode: vi.fn(),
    roomReady: false,
    setRoomReady: vi.fn(),
    movies: true,
    setMovies: vi.fn(),
    tvShows: false,
    setTvShows: vi.fn(),
    isSoloMode: false,
    setIsSoloMode: vi.fn(),
    userInputCode: "",
    setUserInputCode: vi.fn(),
    genre: "All",
    setGenre: vi.fn(),
    hideWatched: false,
    setHideWatched: vi.fn(),
    // The real setters are React.Dispatch<SetStateAction<…>>; a bare vi.fn()
    // is structurally close enough for tests, so we assert the object matches
    // the interface with a single cast here rather than casting each field.
  } as unknown as RoomContextType;
}

export interface RenderWithRoomResult
  extends ReturnType<typeof render> {
  // The context object we provided — return it so tests can both read the
  // preset values and assert on the setter spies.
  ctx: RoomContextType;
}

export function renderWithRoom(
  ui: ReactElement,
  overrides: Partial<RoomContextType> = {},
): RenderWithRoomResult {
  const ctx: RoomContextType = { ...makeDefaultCtx(), ...overrides };
  const result = render(
    <RoomContext.Provider value={ctx}>{ui}</RoomContext.Provider>,
  );
  return { ...result, ctx };
}

// A stateful variant of the helper for tests that need user interactions to
// actually update the context values (checkbox toggles followed by submit).
export function renderWithRoomStateful(
  ui: ReactElement,
  overrides: Partial<RoomContextType> = {},
): RenderWithRoomResult {
  function Provider({ children }: { children: React.ReactNode }) {
    const [movies, setMoviesState] = useState<boolean>(
      overrides.movies ?? true,
    );
    const [tvShows, setTvShowsState] = useState<boolean>(
      overrides.tvShows ?? false,
    );
    const [isSoloMode, setIsSoloModeState] = useState<boolean>(
      overrides.isSoloMode ?? false,
    );
    const [roomReady, setRoomReadyState] = useState<boolean>(
      overrides.roomReady ?? false,
    );
    const [currentRoomCode, setCurrentRoomCodeState] = useState<
      string | null
    >(overrides.currentRoomCode ?? null);
    const [userInputCode, setUserInputCodeState] = useState<string>(
      overrides.userInputCode ?? "",
    );
    const [genre, setGenreState] = useState<string>(
      overrides.genre ?? "All",
    );
    const [hideWatched, setHideWatchedState] = useState<boolean>(
      overrides.hideWatched ?? false,
    );

    const ctx: RoomContextType = {
      currentRoomCode,
      setCurrentRoomCode: vi.fn((v: string | null) =>
        setCurrentRoomCodeState(v as string | null),
      ),
      roomReady,
      setRoomReady: vi.fn((v: boolean) => setRoomReadyState(v)),
      movies,
      setMovies: vi.fn((v: boolean) => setMoviesState(v)),
      tvShows,
      setTvShows: vi.fn((v: boolean) => setTvShowsState(v)),
      isSoloMode,
      setIsSoloMode: vi.fn((v: boolean) => setIsSoloModeState(v)),
      userInputCode,
      setUserInputCode: vi.fn((v: string) => setUserInputCodeState(v)),
      genre,
      setGenre: vi.fn((v: string) => setGenreState(v)),
      hideWatched,
      setHideWatched: vi.fn((v: boolean) => setHideWatchedState(v)),
    } as unknown as RoomContextType;

    return (
      <RoomContext.Provider value={ctx}>{children}</RoomContext.Provider>
    );
  }

  const result = render(<Provider>{ui}</Provider>);
  // We cannot return the exact ctx object here (it is recreated per render),
  // but tests that need it can still rely on the provider's behavior; return a
  // minimal shape where setters are spies by reading from the DOM or mocking
  // when necessary. For simplicity, return an object with spy placeholders.
  const ctx = { ...makeDefaultCtx(), ...overrides } as RoomContextType;
  return { ...result, ctx };
}
