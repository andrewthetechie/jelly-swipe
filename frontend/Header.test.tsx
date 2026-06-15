
import { screen } from "@testing-library/react";
import Header from "./Header";
import { renderWithRoom } from "./test/renderWithRoom";

describe("Header", () => {
  it("renders the logo when roomReady is false", () => {
    // Default ctx has roomReady: null → we're on the landing screen.
    renderWithRoom(<Header />);
    expect(screen.getByAltText("Jelly-Swipe logo")).toBeInTheDocument();
  });

  it("hides the logo once roomReady is true", () => {
    renderWithRoom(<Header />, { roomReady: true });
    // queryBy… returns null (rather than throwing) when nothing matches — the
    // correct matcher for asserting absence.
    expect(screen.queryByAltText("Jelly-Swipe logo")).not.toBeInTheDocument();
  });
});
