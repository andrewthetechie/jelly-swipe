import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import HostModal from "./HostModal";
import { renderWithRoom, renderWithRoomStateful } from "./test/renderWithRoom";
import * as roomApi from "./roomApi";

function getRoomState() {
  return JSON.parse(screen.getByTestId("room-state").textContent ?? "{}");
}

vi.mock("./roomApi", () => ({
  createRoom: vi.fn(),
}));

const createRoomMock = vi.mocked(roomApi.createRoom);

beforeEach(() => {
  vi.clearAllMocks();
  createRoomMock.mockResolvedValue({ pairing_code: "4321" });
});

describe("HostModal — toggles", () => {
  it("clicking Movies (default on) reports the new unchecked value", async () => {
    const user = userEvent.setup();
    renderWithRoomStateful(<HostModal onClose={vi.fn()} />, {
      movies: true,
    });
    await user.click(screen.getByRole("checkbox", { name: /movies/i }));
    expect(screen.getByRole("checkbox", { name: /movies/i })).not.toBeChecked();
  });

  it("clicking the TV toggle (input name='tvShows') drives setTvShows", async () => {
    const user = userEvent.setup();
    renderWithRoomStateful(<HostModal onClose={vi.fn()} />, {
      tvShows: false,
    });
    await user.click(screen.getByRole("checkbox", { name: /tv shows/i }));
    expect(screen.getByRole("checkbox", { name: /tv shows/i })).toBeChecked();
  });

  it("clicking Solo drives setIsSoloMode", async () => {
    const user = userEvent.setup();
    renderWithRoomStateful(<HostModal onClose={vi.fn()} />, {
      isSoloMode: false,
    });
    await user.click(screen.getByRole("checkbox", { name: /solo/i }));
    expect(screen.getByRole("checkbox", { name: /solo/i })).toBeChecked();
  });

  it("calls onClose when Cancel is clicked", async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()

    renderWithRoom(<HostModal onClose={onClose} />)

    const cancelButton = screen.getByRole("button", { name: /cancel/i })
    await user.click(cancelButton)

    expect(onClose).toHaveBeenCalledTimes(1)
    expect(cancelButton).toHaveAttribute("data-modal-type", "host")
  })
});

describe("HostModal — create session (3-part network contract)", () => {
  it("disables Create Session while submitting and prevents double-submit", async () => {
    const user = userEvent.setup()
    let resolveCreate!: (value: { pairing_code: string }) => void
    createRoomMock.mockImplementationOnce(
      () =>
        new Promise<{ pairing_code: string }>((resolve) => {
          resolveCreate = resolve
        }),
    )
    renderWithRoomStateful(<HostModal onClose={vi.fn()} />)

    const createButton = screen.getByRole("button", { name: /create session/i })
    expect(createButton).toBeEnabled()

    await user.click(createButton)

    expect(createButton).toBeDisabled()
    expect(createButton).toHaveTextContent("Creating Session...")

    await user.click(createButton)
    expect(createRoomMock).toHaveBeenCalledTimes(1)

    resolveCreate({ pairing_code: "4321" })

    await waitFor(() => expect(getRoomState()).toMatchObject({ currentRoomCode: "4321" }))
    await waitFor(() => expect(createButton).toBeEnabled());
  })

  it("calls createRoom with {movies, tvShows, solo} and stores pairing_code", async () => {
    const user = userEvent.setup();
    renderWithRoomStateful(<HostModal onClose={vi.fn()} />, {
      movies: true,
      tvShows: false,
      isSoloMode: false,
    });

    await user.click(screen.getByRole("button", { name: /create session/i }));

    await waitFor(() => expect(createRoomMock).toHaveBeenCalledTimes(1));
    expect(createRoomMock).toHaveBeenCalledWith({
      movies: true,
      tvShows: false,
      solo: false,
    });

    await waitFor(() => expect(getRoomState()).toMatchObject({ currentRoomCode: "4321" }))
  });

  it("reflects overridden context values in createRoom payload", async () => {
    const user = userEvent.setup();
    renderWithRoom(<HostModal onClose={vi.fn()} />, {
      movies: false,
      tvShows: true,
      isSoloMode: true,
    });

    await user.click(screen.getByRole("button", { name: /create session/i }));

    await waitFor(() => expect(createRoomMock).toHaveBeenCalledTimes(1));
    expect(createRoomMock).toHaveBeenCalledWith({
      movies: false,
      tvShows: true,
      solo: true,
    })
  });

  it("submits updated movies option after toggling before create", async () => {
    const user = userEvent.setup()

    renderWithRoomStateful(<HostModal onClose={vi.fn()} />, {
      movies: true,
      tvShows: true,
      isSoloMode: false,
    })

    await user.click(screen.getByRole("checkbox", { name: /movies/i }))
    await user.click(screen.getByRole("button", { name: /create session/i }))

    await waitFor(() => expect(createRoomMock).toHaveBeenCalledTimes(1))
    expect(createRoomMock).toHaveBeenCalledWith({
      movies: false,
      tvShows: true,
      solo: false,
    })
  })

  it("submits updated tvShows option after toggling before create", async () => {
    const user = userEvent.setup()

    renderWithRoomStateful(<HostModal onClose={vi.fn()} />, {
      movies: true,
      tvShows: true,
      isSoloMode: false,
    })

    await user.click(screen.getByRole("checkbox", { name: /tv shows/i }))
    await user.click(screen.getByRole("button", { name: /create session/i }))

    await waitFor(() => expect(createRoomMock).toHaveBeenCalledTimes(1))
    expect(createRoomMock).toHaveBeenCalledWith({
      movies: true,
      tvShows: false,
      solo: false,
    })
  })  

  it("submits updated isSoloMode option after toggling before create", async () => {
    const user = userEvent.setup()

    renderWithRoomStateful(<HostModal onClose={vi.fn()} />, {
      movies: true,
      tvShows: true,
      isSoloMode: false,
    })

    await user.click(screen.getByRole("checkbox", { name: /solo/i }))
    await user.click(screen.getByRole("button", { name: /create session/i }))

    await waitFor(() => expect(createRoomMock).toHaveBeenCalledTimes(1))
    expect(createRoomMock).toHaveBeenCalledWith({
      movies: true,
      tvShows: true,
      solo: true,
    })
  })

  it("does not set a room code and does not throw when the request returns non-ok", async () => {
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const user = userEvent.setup();
    createRoomMock.mockRejectedValueOnce(new Error("Error creating session: 500 Server Error"));
    renderWithRoomStateful(<HostModal onClose={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: /create session/i }));

    await waitFor(() => expect(errSpy).toHaveBeenCalled());
    expect(getRoomState()).toMatchObject({ currentRoomCode: null });

    errSpy.mockRestore();
  });

  it("does not set a room code when fetch rejects", async () => {
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {})
    const user = userEvent.setup()
    createRoomMock.mockRejectedValueOnce(new Error("network error"))
    renderWithRoomStateful(<HostModal onClose={vi.fn()} />)

    await user.click(screen.getByRole("button", { name: /create session/i }))

    await waitFor(() => expect(createRoomMock).toHaveBeenCalledTimes(1))
    expect(getRoomState()).toMatchObject({ currentRoomCode: null })
    expect(errSpy).toHaveBeenCalled()

    errSpy.mockRestore()
  })
});
