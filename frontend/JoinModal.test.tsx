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
import * as roomApi from "./roomApi";

function getRoomState() {
  return JSON.parse(screen.getByTestId("room-state").textContent ?? "{}");
}

vi.mock("./roomApi", () => ({
  joinRoom: vi.fn(),
}));

const joinRoomMock = vi.mocked(roomApi.joinRoom);

beforeEach(() => {
  vi.clearAllMocks();
  joinRoomMock.mockResolvedValue({ status: "ok" });
});

describe("JoinModal — input sanitization", () => {
  it("strips non-digits and preserves digit order (asserted via the setter spy)", () => {
    renderWithRoom(<JoinModal onClose={vi.fn()} />, {
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
    expect(screen.getByPlaceholderText("Enter Host Code")).toHaveValue("123");
    expect(getRoomState()).toMatchObject({ userInputCode: "123" });
  });
});

describe("JoinModal — cancel button", () => {
  it("calls onClose when Cancel is clicked", async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()

    renderWithRoom(<JoinModal onClose={onClose} />)

    const cancelButton = screen.getByRole("button", { name: /cancel/i })
    await user.click(cancelButton)

    expect(onClose).toHaveBeenCalledTimes(1)
    expect(cancelButton).toHaveAttribute("data-modal-type", "join")
  })
})

describe("JoinModal — join (3-part network contract)", () => {
  it("does not submit when room code length is not 4", async () => {
    const user = userEvent.setup()
    renderWithRoom(<JoinModal onClose={vi.fn()} />, {
      userInputCode: "12",
    })

    const joinButton = screen.getByRole("button", { name: /join session/i })
    expect(joinButton).toBeDisabled()

    await user.click(joinButton)

    expect(joinRoomMock).not.toHaveBeenCalled()
    expect(getRoomState()).toMatchObject({ currentRoomCode: null })
  })

  it("calls joinRoom with the code and sets the room code on success", async () => {
    const user = userEvent.setup();
    renderWithRoom(<JoinModal onClose={vi.fn()} />, {
      userInputCode: "1234",
    });

    await user.click(screen.getByRole("button", { name: /join session/i }));

    await waitFor(() => expect(joinRoomMock).toHaveBeenCalledTimes(1));
    expect(joinRoomMock).toHaveBeenCalledWith("1234");

    await waitFor(() => expect(getRoomState()).toMatchObject({ currentRoomCode: "1234" }));
  });

  it("does not set a room code and does not throw when the request returns non-ok", async () => {
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const user = userEvent.setup();
    joinRoomMock.mockRejectedValueOnce(new Error("Error joining room: 500 Server Error"));
    renderWithRoom(<JoinModal onClose={vi.fn()} />, {
      userInputCode: "1234",
    });

    await user.click(screen.getByRole("button", { name: /join session/i }));

    await waitFor(() => expect(errSpy).toHaveBeenCalled());
    expect(getRoomState()).toMatchObject({ currentRoomCode: null });

    errSpy.mockRestore();
  });

  it("does not set a room code and does not throw when the request rejects", async () => {
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const user = userEvent.setup();
    joinRoomMock.mockRejectedValueOnce(new Error("network error"));
    renderWithRoom(<JoinModal onClose={vi.fn()} />, {
      userInputCode: "1234",
    });

    await user.click(screen.getByRole("button", { name: /join session/i }));

    await waitFor(() => expect(joinRoomMock).toHaveBeenCalled());
    expect(getRoomState()).toMatchObject({ currentRoomCode: null });

    errSpy.mockRestore();
  });
});
