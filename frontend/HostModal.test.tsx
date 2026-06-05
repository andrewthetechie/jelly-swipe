// HostModal.test.tsx — covers the host setup toggles and the create-session
// network action.
//
// Things to note:
//   • The checkboxes are UNCONTROLLED (`defaultChecked`), so we don't read their
//     checked state back — we click them and assert the matching context setter
//     spy was called with the NEW boolean.
//   • createSession follows the 3-part network contract (request body included):
//     the request is POST /room with body {movies, tv_shows, solo} built from
//     the context values at render time; success calls setCurrentRoomCode with
//     the returned pairing_code; one failure path leaves it uncalled.
//   • createRoomRequest is computed from context at render, so to test a specific body
//     we preset the context via renderWithRoom overrides.
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import HostModal from "./HostModal";
import { renderWithRoom, renderWithRoomStateful } from "./test/renderWithRoom";
import { mockFetch } from "./test/mockFetch";

describe("HostModal — toggles", () => {
  it("clicking Movies (default on) reports the new unchecked value", async () => {
    const user = userEvent.setup();
    const { ctx } = renderWithRoom(<HostModal onClose={vi.fn()} />, {
      movies: true,
    });
    await user.click(screen.getByRole("checkbox", { name: /movies/i }));
    expect(ctx.setMovies).toHaveBeenCalledWith(false);
  });

  it("clicking the TV toggle (input name='tvShows') drives setTvShows", async () => {
    const user = userEvent.setup();
    const { ctx } = renderWithRoom(<HostModal onClose={vi.fn()} />, {
      tvShows: false,
    });
    await user.click(screen.getByRole("checkbox", { name: /tv shows/i }));
    expect(ctx.setTvShows).toHaveBeenCalledWith(true);
  });

  it("clicking Solo drives setIsSoloMode", async () => {
    const user = userEvent.setup();
    const { ctx } = renderWithRoom(<HostModal onClose={vi.fn()} />, {
      isSoloMode: false,
    });
    await user.click(screen.getByRole("checkbox", { name: /solo/i }));
    expect(ctx.setIsSoloMode).toHaveBeenCalledWith(true);
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
  it("POSTs {movies, tv_shows, solo} to /room and stores the pairing_code", async () => {
    const user = userEvent.setup();
    const spy = mockFetch({ ok: true, body: { pairing_code: "4321" } });
    const { ctx } = renderWithRoom(<HostModal onClose={vi.fn()} />, {
      movies: true,
      tvShows: false,
      isSoloMode: false,
    });

    await user.click(screen.getByRole("button", { name: /create session/i }));

    // 1. The request: URL, method, headers, and the JSON body.
    await waitFor(() => expect(spy).toHaveBeenCalledTimes(1));
    const [url, options] = spy.mock.calls[0];
    expect((url as URL).href).toMatch(/\/room$/);
    const opts = options as RequestInit;
    expect(opts.method).toBe("POST");
    expect(opts.headers).toMatchObject({ "Content-Type": "application/json" });
    expect(JSON.parse(opts.body as string)).toEqual({
      movies: true,
      tv_shows: false,
      solo: false,
    });

    // 2. The success effect: the returned pairing_code becomes the room code.
    await waitFor(() =>
      expect(ctx.setCurrentRoomCode).toHaveBeenCalledWith("4321"),
    );
  });

  it("reflects overridden context values in the request body", async () => {
    const user = userEvent.setup();
    const spy = mockFetch({ ok: true, body: { pairing_code: "4321" } });
    renderWithRoom(<HostModal onClose={vi.fn()} />, {
      movies: false,
      tvShows: true,
      isSoloMode: true,
    });

    await user.click(screen.getByRole("button", { name: /create session/i }));

    await waitFor(() => expect(spy).toHaveBeenCalledTimes(1));
    const [, options] = spy.mock.calls[0];
    expect(JSON.parse((options as RequestInit).body as string)).toEqual({
      movies: false,
      tv_shows: true,
      solo: true,
    });
  });

  it("submits updated movies option after toggling before create", async () => {
    const user = userEvent.setup()
    const spy = mockFetch({ ok: true, body: { pairing_code: "4321" }})

    renderWithRoomStateful(<HostModal onClose={vi.fn()} />, {
      movies: true,
      tvShows: true,
      isSoloMode: false,
    })

    await user.click(screen.getByRole("checkbox", { name: /movies/i }))
    await user.click(screen.getByRole("button", { name: /create session/i }))

    await waitFor(() => expect(spy).toHaveBeenCalledTimes(1))
    const [, options] = spy.mock.calls[0]
    expect(JSON.parse((options as RequestInit).body as string)).toEqual({
      movies: false,
      tv_shows: true,
      solo: false,
    })
  })

  it("submits updated tvShows option after toggling before create", async () => {
    const user = userEvent.setup()
    const spy = mockFetch({ ok: true, body: { pairing_code: "4321" }})

    renderWithRoomStateful(<HostModal onClose={vi.fn()} />, {
      movies: true,
      tvShows: true,
      isSoloMode: false,
    })

    await user.click(screen.getByRole("checkbox", { name: /tv shows/i }))
    await user.click(screen.getByRole("button", { name: /create session/i }))

    await waitFor(() => expect(spy).toHaveBeenCalledTimes(1))
    const [, options] = spy.mock.calls[0]
    expect(JSON.parse((options as RequestInit).body as string)).toEqual({
      movies: true,
      tv_shows: false,
      solo: false,
    })
  })  

  it("submits updated isSoloMode option after toggling before create", async () => {
    const user = userEvent.setup()
    const spy = mockFetch({ ok: true, body: { pairing_code: "4321" }})

    renderWithRoomStateful(<HostModal onClose={vi.fn()} />, {
      movies: true,
      tvShows: true,
      isSoloMode: false,
    })

    await user.click(screen.getByRole("checkbox", { name: /solo/i }))
    await user.click(screen.getByRole("button", { name: /create session/i }))

    await waitFor(() => expect(spy).toHaveBeenCalledTimes(1))
    const [, options] = spy.mock.calls[0]
    expect(JSON.parse((options as RequestInit).body as string)).toEqual({
      movies: true,
      tv_shows: true,
      solo: true,
    })
  })

  it("does not set a room code and does not throw when the request returns non-ok", async () => {
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const user = userEvent.setup();
    const spy = mockFetch({ ok: false });
    const { ctx } = renderWithRoom(<HostModal onClose={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: /create session/i }));

    await waitFor(() => expect(errSpy).toHaveBeenCalled());
    expect(ctx.setCurrentRoomCode).not.toHaveBeenCalled();

    errSpy.mockRestore();
  });

  it("does not set a room code when fetch rejects", async () => {
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {})
    const user = userEvent.setup()
    const spy = mockFetch({ reject: true })
    const { ctx } = renderWithRoom(<HostModal onClose={vi.fn()} />)

    await user.click(screen.getByRole("button", { name: /create session/i }))

    await waitFor(() => expect(spy).toHaveBeenCalledTimes(1))
    expect(ctx.setCurrentRoomCode).not.toHaveBeenCalled()
    expect(errSpy).toHaveBeenCalled()

    errSpy.mockRestore()
  })
});
