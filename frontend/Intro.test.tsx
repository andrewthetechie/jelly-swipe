// Intro.test.tsx — covers the landing screen's modal open/close behaviour and
// the context state it RESETS when a modal is cancelled.
//
// Two ideas to take away here:
//   • `showHostModal` / `showJoinModal` are LOCAL state in Intro, so "the modal
//     opened" is asserted by the modal appearing in the DOM — not by spying on
//     a setter. "State was reset on close" is the opposite: it lives in context,
//     so we assert it via the `vi.fn()` setter spies that renderWithRoom hands us.
//   • Intro renders <HostModal>/<JoinModal> as children, and THEY also call
//     useRoomContext(), so renderWithRoom (providing the real context) is
//     required — a plain render() would throw.
//
// We use @testing-library/user-event for clicks because it models real user
// interaction (focus, pointer, etc.) more faithfully than fireEvent. We don't
// assert anything about the modals' internal fields here — those belong to the
// HostModal/JoinModal tests (issues 07/08).
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Intro from "./Intro";
import { renderWithRoom } from "./test/renderWithRoom";

describe("Intro — modal open/close + state reset", () => {
  it("opens the host modal when the Host button is clicked", async () => {
    const user = userEvent.setup();
    renderWithRoom(<Intro />);

    await user.click(screen.getByRole("button", { name: /host/i }));
    expect(screen.getByText("Session Setup")).toBeInTheDocument();
  });

  it("opens the join modal when the Join button is clicked", async () => {
    const user = userEvent.setup();
    renderWithRoom(<Intro />);

    await user.click(screen.getByRole("button", { name: /join/i }));
    expect(screen.getByText("Enter Room Code")).toBeInTheDocument();
  });

  it("resets host options and closes when the host modal is cancelled", async () => {
    const user = userEvent.setup();
    const { ctx } = renderWithRoom(<Intro />);

    await user.click(screen.getByRole("button", { name: /host/i }));
    // The host modal's Cancel control carries data-modal-type="host".
    await user.click(screen.getByText("Cancel"));

    // Closing resets the host-related context to its defaults…
    expect(ctx.setMovies).toHaveBeenCalledWith(true);
    expect(ctx.setTvShows).toHaveBeenCalledWith(false);
    expect(ctx.setIsSoloMode).toHaveBeenCalledWith(false);
    // …and the modal is gone.
    expect(screen.queryByText("Session Setup")).not.toBeInTheDocument();
  });

  it("clears the entered code and closes when the join modal is cancelled", async () => {
    const user = userEvent.setup();
    const { ctx } = renderWithRoom(<Intro />);

    await user.click(screen.getByRole("button", { name: /join/i }));
    await user.click(screen.getByText("Cancel"));

    expect(ctx.setUserInputCode).toHaveBeenCalledWith("");
    expect(screen.queryByText("Enter Room Code")).not.toBeInTheDocument();
  });
});
