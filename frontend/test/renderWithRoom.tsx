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
import { RoomContext, type RoomContextType } from "../RoomContextProvider";

// Build a default context: plausible starting values plus a vi.fn() spy for
// every setter. Tests can override any field via the second argument.
function makeDefaultCtx(): RoomContextType {
  return {
    currentRoomCode: null,
    setCurrentRoomCode: vi.fn(),
    movies: true,
    setMovies: vi.fn(),
    tvShows: false,
    setTvShows: vi.fn(),
    isSoloMode: false,
    setIsSoloMode: vi.fn(),
    userInputCode: "",
    setUserInputCode: vi.fn(),
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
