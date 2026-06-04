// Header.test.tsx — the first test in the suite, and the simplest worked
// example of the whole pattern.
//
// What Header does: it renders the logo image, but ONLY when there is no room
// code yet (the landing screen). Once you're in a room, the logo is hidden.
// That conditional IS the behaviour, so we test both branches:
//   - no room code  → logo present
//   - room code set → logo absent
//
// How: we render with `renderWithRoom` (from test/renderWithRoom.tsx) because
// Header calls `useRoomContext()` and would throw without a provider. We preset
// `currentRoomCode` via the overrides argument to drive each branch. We find the
// logo by its accessible alt text (`getByAltText`), which is how a screen reader
// — and therefore a user — identifies the image; `queryBy…` returns null instead
// of throwing, which is what we want when asserting something is ABSENT.
import { screen } from "@testing-library/react";
import Header from "./Header";
import { renderWithRoom } from "./test/renderWithRoom";

describe("Header", () => {
  it("renders the logo when there is no room code", () => {
    // Default ctx has currentRoomCode: null → we're on the landing screen.
    renderWithRoom(<Header />);
    expect(screen.getByAltText("Jelly-Swipe logo")).toBeInTheDocument();
  });

  it("hides the logo once a room code is set", () => {
    renderWithRoom(<Header />, { currentRoomCode: "1234" });
    // queryBy… returns null (rather than throwing) when nothing matches — the
    // correct matcher for asserting absence.
    expect(screen.queryByAltText("Jelly-Swipe logo")).not.toBeInTheDocument();
  });
});
