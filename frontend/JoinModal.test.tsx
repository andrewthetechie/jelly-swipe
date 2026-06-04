// JoinModal.test.tsx — covers the room-code input sanitization and the join
// network action.
//
// Worth understanding:
//   • The room code now lives in CONTEXT (`userInputCode` / `setUserInputCode`),
//     not local state. The input is therefore CONTROLLED by the context value.
//     In tests, `setUserInputCode` is a vi.fn() spy that does NOT update state,
//     so the input's value stays put — meaning we can't read sanitized text back
//     out of the DOM, AND a `user.type("a1b2")` would only ever deliver ONE
//     character per onChange (the value never accumulates). To actually exercise
//     the regex on a real multi-character string we fire a single `change` event
//     carrying the full mixed value and assert the spy received the sanitized,
//     digit-only, in-order result.
//   • joinRoom follows the 3-part network contract: POST
//     /room/{userInputCode}/join; success → setCurrentRoomCode(userInputCode);
//     one failure path leaves it uncalled. We preset userInputCode via overrides.
import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import JoinModal from "./JoinModal";
import { renderWithRoom } from "./test/renderWithRoom";
import { mockFetch } from "./test/mockFetch";

describe("JoinModal — input sanitization", () => {
  it("strips non-digits and preserves digit order (asserted via the setter spy)", () => {
    const { ctx } = renderWithRoom(<JoinModal onClose={vi.fn()} />, {
      userInputCode: "",
    });

    // One change with a mixed value — letters interleaved with digits — so the
    // `value.replace(/[^0-9]/g, '')` regex is tested on a genuine multi-char
    // string rather than the single characters a controlled-input `type()`
    // would produce.
    fireEvent.change(screen.getByPlaceholderText("Enter Host Code"), {
      target: { value: "1a2b3" },
    });

    // Letters dropped, digits kept in order.
    expect(ctx.setUserInputCode).toHaveBeenLastCalledWith("123");
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
