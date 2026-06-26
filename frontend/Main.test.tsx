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
import { screen, waitFor, fireEvent } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import Main from "./Main"
import SwipePage from "./SwipePage"
import { renderWithRoom } from "./test/renderWithRoom"
import { SSEContextProvider } from "./SSEContextProvider"
import { mockFetch } from "./test/mockFetch"
import { makeDeck, makeCard, swipeRight, swipeLeft } from "./test/fixtures"
import { type CardDeck } from "./types"


describe("Main — screen switching", () => {
  it("renders Intro (not SwipePage) when there is no room code", async () => {
    // Mock fetch so the mount-time effect (fetching /room/null/deck) is inert.
    mockFetch({ ok: true, body: [] })
    renderWithRoom(
      <SSEContextProvider>
        <Main />
      </SSEContextProvider>, 
      { currentRoomCode: null }
    )

    // Use findBy… (async) rather than getBy… so the mount effect's eventual
    // setCardDeck([]) flushes inside React's act() — otherwise React logs a
    // harmless-but-noisy "not wrapped in act(...)" warning.
    expect(
      await screen.findByRole("button", { name: /host/i }),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: /end session/i }),
    ).not.toBeInTheDocument()
  })
})

describe("Main — deck fetch (3-part network contract)", () => {
  it("GETs /room/{code}/deck and renders the returned cards in SwipePage", async () => {
    const spy = mockFetch({ ok: true, body: makeDeck(3) })
    renderWithRoom(
      <SSEContextProvider>
        <Main />
      </SSEContextProvider>, 
      { currentRoomCode: "1234", roomReady: true }
    )

    // SwipePage is the active screen once a code is set.
    expect(
      screen.getByRole("button", { name: /end session/i }),
    ).toBeInTheDocument()

    // 1. The request: GET to /room/1234/deck.
    const [url, options] = spy.mock.calls[0]
    expect((url as URL).href).toMatch(/\/room\/1234\/deck$/)
    expect((options as RequestInit).method).toBe("GET")

    // 2. The success effect: the 3 fetched cards render (await the async effect).
    const posters = await screen.findAllByAltText(/^Movie \d$/)
    expect(posters).toHaveLength(3)
  })

  it("renders no cards and does not crash when the fetch fails", async () => {
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {})
    mockFetch({ ok: false })
    const { container } = renderWithRoom(
      <SSEContextProvider>
        <Main />
      </SSEContextProvider>, 
      { currentRoomCode: "1234" }
    )

    // SwipePage still mounts, but with an empty deck — so no cards render.
    expect(
      screen.getByRole("button", { name: /end session/i }),
    ).toBeInTheDocument()
    expect(container.querySelectorAll(".card-item-container")).toHaveLength(0)

    errSpy.mockRestore()
  })

  it("renders no cards and does not crash when the fetch rejects", async () => {
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {})
    mockFetch({ reject: true })
    const { container } = renderWithRoom(
      <SSEContextProvider>
        <Main />
      </SSEContextProvider>, 
      { currentRoomCode: "1234" }
    )

    expect(
      screen.getByRole("button", { name: /end session/i }),
    ).toBeInTheDocument()
    await waitFor(() =>
      expect(container.querySelectorAll(".card-item-container")).toHaveLength(0),
    )

    errSpy.mockRestore()
  })
})

describe("Main - swipe handling", () => {
  it("successful swipe POSTs and removes the top card", async () => {
    const deck = makeDeck(3)
    const fetchSpy = vi.spyOn(globalThis, "fetch")

    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: async () => deck,
    } as Response)

    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ success: true }),
    } as Response)

    renderWithRoom(
      <SSEContextProvider>
        <Main />
      </SSEContextProvider>,
      { currentRoomCode: "1234", roomReady: true }
    )

    // Check that the deck has appeared
    expect(await screen.findByAltText("Movie 1")).toBeInTheDocument()
    expect(screen.getByAltText("Movie 2")).toBeInTheDocument()

    const cards = document.querySelectorAll(".card-item-container")
    expect(cards).toHaveLength(3)
    const topCard = cards[cards.length - 1] as HTMLElement

    // Perform swipe
    await swipeRight(topCard)

    // Verify POST happened
    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledTimes(2)
    })

    const [, options] = fetchSpy.mock.calls[1]

    expect((options as RequestInit).method).toBe("POST")

    // Verify movie 1 disappeared
    await waitFor(() => {
      expect(
        screen.queryByAltText("Movie 1")
      ).not.toBeInTheDocument()
    })

    // Verify that movie 2 is now top card
    expect(screen.getByAltText("Movie 2")).toBeInTheDocument()
  })

  it("succesful swipe POSTs with correct body", async () => {
    const deck = makeDeck(3)
    const fetchSpy = vi.spyOn(globalThis, "fetch")

    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: async () => deck,
    } as Response)

    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ success: true }),
    } as Response)

    renderWithRoom(
      <SSEContextProvider>
        <Main />
      </SSEContextProvider>,
      { currentRoomCode: "1234", roomReady: true }
    )

    // Check that the deck has appeared
    expect(await screen.findByAltText("Movie 1")).toBeInTheDocument()
    expect(screen.getByAltText("Movie 2")).toBeInTheDocument()

    const cards = document.querySelectorAll(".card-item-container")
    expect(cards).toHaveLength(3)
    const topCard = cards[cards.length - 1] as HTMLElement

    // Perform swipe
    await swipeRight(topCard)

    // Verify POST and body matches top card and direction
    await waitFor(() => {
      expect(fetchSpy).toHaveBeenNthCalledWith(
        2,
        expect.any(URL),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            media_id: "1",
            direction: "right",
          }),
        }),
      )
    })
  })

  it("succesful swipe POSTs with correct URL", async () => {
    const deck = makeDeck(3)
    const fetchSpy = vi.spyOn(globalThis, "fetch")

    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: async () => deck,
    } as Response)

    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ success: true }),
    } as Response)

    renderWithRoom(
      <SSEContextProvider>
        <Main />
      </SSEContextProvider>,
      { currentRoomCode: "1234", roomReady: true }
    )

    // Check that the deck has appeared
    expect(await screen.findByAltText("Movie 1")).toBeInTheDocument()
    expect(screen.getByAltText("Movie 2")).toBeInTheDocument()

    const cards = document.querySelectorAll(".card-item-container")
    expect(cards).toHaveLength(3)
    const topCard = cards[cards.length - 1] as HTMLElement

    // Perform swipe
    await swipeRight(topCard)    

    // Verify URL matches expected endpoint
    const swipeUrl = fetchSpy.mock.calls[1][0] as URL
    expect(swipeUrl.href).toMatch(
      /\/room\/1234\/swipe$/
    )
  })

  it("does not advance deck when the swipe request fails", async () => {
    const deck = makeDeck(3)
    const fetchSpy = vi.spyOn(globalThis, "fetch")
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {})

    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: async () => deck,
    } as Response)

    fetchSpy.mockResolvedValueOnce({
      ok: false,
      json: async () => ({ reject: true }),
    } as Response)

    renderWithRoom(
      <SSEContextProvider>
        <Main />
      </SSEContextProvider>,
      { currentRoomCode: "1234", roomReady: true }
    )

    // Check that the deck has appeared
    expect(await screen.findByAltText("Movie 1")).toBeInTheDocument()
    expect(screen.getByAltText("Movie 2")).toBeInTheDocument()

    const cards = document.querySelectorAll(".card-item-container")
    expect(cards).toHaveLength(3)
    const topCard = cards[cards.length - 1] as HTMLElement

    // Perform swipe
    await swipeRight(topCard)

    // Verify POST happened
    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledTimes(2)
    })

    const [, options] = fetchSpy.mock.calls[1]

    expect((options as RequestInit).method).toBe("POST")
    expect((options as RequestInit).body).toBe(
      JSON.stringify({
        media_id: deck[0].media_id,
        direction: "right",
      })
    )

    // Verify movie 1 is still in the document
    expect(screen.queryByAltText("Movie 1")).toBeInTheDocument()
    
    errSpy.mockRestore()
  })
})



// LATER
// add test ID to top card: 
// data-testid={isTopCard ? "top-card" : undefined}

// then test:
// const topCard = screen.getByTestId("top-card")
// await swipeRight(topCard)
