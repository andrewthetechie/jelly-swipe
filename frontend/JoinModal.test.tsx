// JoinModal.test.tsx — covers the room-code input sanitization and the join
// network action.
//
// Worth understanding:
//   • The room code now lives in CONTEXT (`userInputCode` / `setUserInputCode`),
//     not local state. The input is therefore CONTROLLED by the context value.
//     In tests, `setUserInputCode` is a vi.fn() spy that does NOT update state,
//     so the input's value stays put — meaning we can't read sanitized text back
//     out of the DOM. Instead we assert sanitization through the SPY's
//     arguments: every onChange strips non-digits via
//     `value.replace(/[^0-9]/g, '')`, so every call arg must be digit-only.
//   • joinRoom follows the 3-part network contract: POST
//     /room/{userInputCode}/join; success → setCurrentRoomCode(userInputCode);
//     one failure path leaves it uncalled. We preset userInputCode via overrides.
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import JoinModal from "./JoinModal";
import { renderWithRoom } from "./test/renderWithRoom";
import { mockFetch } from "./test/mockFetch";

describe("JoinModal — input sanitization", () => {
  it("strips non-digits on every keystroke (asserted via the setter spy)", async () => {
    const user = userEvent.setup();
    const { ctx } = renderWithRoom(<JoinModal onClose={vi.fn()} />, {
      userInputCode: "",
    });

    await user.type(screen.getByPlaceholderText("Enter Host Code"), "a1b2");

    // At least one change fired, and EVERY value passed to setUserInputCode is
    // digits-only (letters were stripped before the setter ran).
    expect(ctx.setUserInputCode).toHaveBeenCalled();
    for (const call of (ctx.setUserInputCode as ReturnType<typeof vi.fn>).mock
      .calls) {
      expect(call[0]).toMatch(/^[0-9]*$/);
    }
  });
});

describe("JoinModal — join (3-part network contract)", () => {
  it("POSTs to /room/{code}/join and sets the room code on success", async () => {
    const user = userEvent.setup();
    const spy = mockFetch({ ok: true, body: { status: "ok" } });
    const { ctx } = renderWithRoom(<JoinModal onClose={vi.fn()} />, {
      userInputCode: "1234",
    });

    await user.click(screen.getByRole("button", { name: /join session/i }));

    // 1. The request: URL ends /room/1234/join, POST, JSON content type.
    await waitFor(() => expect(spy).toHaveBeenCalledTimes(1));
    const [url, options] = spy.mock.calls[0];
    expect((url as URL).href).toMatch(/\/room\/1234\/join$/);
    const opts = options as RequestInit;
    expect(opts.method).toBe("POST");
    expect(opts.headers).toMatchObject({ "Content-Type": "application/json" });

    // 2. The success effect: the entered code becomes the current room code.
    await waitFor(() =>
      expect(ctx.setCurrentRoomCode).toHaveBeenCalledWith("1234"),
    );
  });

  it("does not set a room code and does not throw when the request rejects", async () => {
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const user = userEvent.setup();
    const spy = mockFetch({ reject: true });
    const { ctx } = renderWithRoom(<JoinModal onClose={vi.fn()} />, {
      userInputCode: "1234",
    });

    await user.click(screen.getByRole("button", { name: /join session/i }));

    // 3. The failure path: request attempted, success effect never runs.
    await waitFor(() => expect(spy).toHaveBeenCalled());
    expect(ctx.setCurrentRoomCode).not.toHaveBeenCalled();

    errSpy.mockRestore();
  });
});
