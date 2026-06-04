// Main.test.tsx — covers the top-level screen switch (Intro vs. SwipePage) and
// the deck fetch that runs on mount.
//
// Things to know:
//   • Main shows <Intro /> when there's no room code and <SwipePage /> once one
//     is set. We assert each branch by a marker element (the Host button vs. the
//     End Session button).
//   • A useEffect (deps [currentRoomCode]) fetches the deck via
//     apiFetch('/room/{code}/deck', GET) and stores it; SwipePage then renders
//     those cards. Because that's ASYNC, we await it with findAllBy… queries
//     (which retry until the element appears) rather than getAllBy… (which would
//     check once, before the fetch resolves).
//   • The effect ALSO fires on first mount when the code is null (it would fetch
//     /room/null/deck). We don't over-specify that; we just mock fetch in every
//     test so no test touches the real network, and focus assertions on the
//     code-set path. checkSessionStatus is commented out in the source and is
//     intentionally untested.
import { screen } from "@testing-library/react";
import Main from "./Main";
import { renderWithRoom } from "./test/renderWithRoom";
import { mockFetch } from "./test/mockFetch";
import { makeDeck } from "./test/fixtures";

describe("Main — screen switching", () => {
  it("renders Intro (not SwipePage) when there is no room code", async () => {
    // Mock fetch so the mount-time effect (fetching /room/null/deck) is inert.
    mockFetch({ ok: true, body: [] });
    renderWithRoom(<Main />, { currentRoomCode: null });

    // Use findBy… (async) rather than getBy… so the mount effect's eventual
    // setCardDeck([]) flushes inside React's act() — otherwise React logs a
    // harmless-but-noisy "not wrapped in act(...)" warning.
    expect(
      await screen.findByRole("button", { name: /host/i }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /end session/i }),
    ).not.toBeInTheDocument();
  });
});

describe("Main — deck fetch (3-part network contract)", () => {
  it("GETs /room/{code}/deck and renders the returned cards in SwipePage", async () => {
    const spy = mockFetch({ ok: true, body: makeDeck(3) });
    renderWithRoom(<Main />, { currentRoomCode: "1234" });

    // SwipePage is the active screen once a code is set.
    expect(
      screen.getByRole("button", { name: /end session/i }),
    ).toBeInTheDocument();

    // 1. The request: GET to /room/1234/deck.
    const [url, options] = spy.mock.calls[0];
    expect((url as URL).href).toMatch(/\/room\/1234\/deck$/);
    expect((options as RequestInit).method).toBe("GET");

    // 2. The success effect: the 3 fetched cards render (await the async effect).
    const posters = await screen.findAllByAltText(/^Movie \d$/);
    expect(posters).toHaveLength(3);
  });

  it("renders no cards and does not crash when the fetch fails", async () => {
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    mockFetch({ ok: false });
    const { container } = renderWithRoom(<Main />, { currentRoomCode: "1234" });

    // SwipePage still mounts, but with an empty deck — so no cards render.
    expect(
      screen.getByRole("button", { name: /end session/i }),
    ).toBeInTheDocument();
    expect(container.querySelectorAll(".movie-card-container")).toHaveLength(0);

    errSpy.mockRestore();
  });
});
