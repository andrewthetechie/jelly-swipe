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
import { screen, waitFor, fireEvent, render } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import Main from "./Main"
import SwipePage from "./SwipePage"
import { RoomContext } from "./RoomContextProvider"
import { renderWithRoom, renderWithRoomStateful } from "./test/renderWithRoom"
import { SSEContextProvider } from "./SSEContextProvider"
import * as useSSEModule from "./useSSE"
import { mockFetch } from "./test/mockFetch"
import { makeDeck, makeCard, swipeRight, swipeLeft } from "./test/fixtures"


async function setupSuccessfulSwipeTest(
  direction: "left" | "right" = "right",
  deck = makeDeck(3),
) {
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

  expect(await screen.findByAltText("Movie 1")).toBeInTheDocument()
  expect(screen.getByAltText("Movie 2")).toBeInTheDocument()

  const cards = document.querySelectorAll(".card-item-container")
  expect(cards).toHaveLength(3)
  const topCard = cards[cards.length - 1] as HTMLElement

  if (direction === "right") {
    await swipeRight(topCard)
  } else {
    await swipeLeft(topCard)
  }

  await waitFor(() => {
    expect(fetchSpy).toHaveBeenCalledTimes(2)
  })

  return {
    deck, 
    fetchSpy,
    topCard,
  }
}

async function setupUndoTest(deck = makeDeck(3)) {
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

  expect(await screen.findByAltText("Movie 1")).toBeInTheDocument()

  const cards = document.querySelectorAll(".card-item-container")
  expect(cards).toHaveLength(3)
  const topCard = cards[cards.length - 1] as HTMLElement

  await swipeLeft(topCard)

  await waitFor(() => {
    expect(fetchSpy).toHaveBeenCalledTimes(2)
  })

  const undoButton = screen.getByRole("button", {
      name: /undo/i,
    })

  return {
    deck, 
    fetchSpy, 
    undoButton,
  }
}

async function setupGenreChangeTest() {
  const user = userEvent.setup()
  const fetchSpy = vi.spyOn(globalThis, "fetch")

  fetchSpy.mockResolvedValueOnce({
    ok: true,
    json: async () => makeDeck(3),
  } as Response)

  fetchSpy.mockResolvedValueOnce({
    ok: true,
    json: async () => [
      "Action",
      "Comedy",
      "Drama",
    ]
  } as Response)

  renderWithRoomStateful(
    <SSEContextProvider>
      <Main />
    </SSEContextProvider>,
    { currentRoomCode: "1234", roomReady: true, genre: "Action",}
  )

  expect(await screen.findByAltText("Movie 1")).toBeInTheDocument()

  await user.click(screen.getByText("Genres"))

  expect(
    await screen.findByLabelText("Comedy")
  ).toBeInTheDocument()

  return {
    user,
    fetchSpy,
  }
}

async function setupWatchedToggleTest() {
  const user = userEvent.setup()
  const fetchSpy = vi.spyOn(globalThis, "fetch")

  fetchSpy.mockResolvedValueOnce({
    ok: true,
    json: async () => makeDeck(3),
  } as Response)

  renderWithRoomStateful(
    <SSEContextProvider>
      <Main />
    </SSEContextProvider>,
    { currentRoomCode: "1234", roomReady: true, }
  )

  expect(await screen.findByAltText("Movie 1")).toBeInTheDocument()

  const toggle = screen.getByRole("checkbox", {
    name: /hide watched/i,
  })

  return {
    user,
    fetchSpy,
    toggle,
  }

}

beforeEach(() => {
  sessionStorage.clear()
})

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
    const { fetchSpy } = await setupSuccessfulSwipeTest()

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

  it("succesful swipe POSTs with correct body and URL", async () => {
    const { deck, fetchSpy } = await setupSuccessfulSwipeTest()

    // Verify POST and body matches top card and direction
    await waitFor(() => {
      expect(fetchSpy).toHaveBeenNthCalledWith(
        2,
        expect.any(URL),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            media_id: deck[0].media_id,
            direction: "right",
          }),
        }),
      )
    })

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

describe("Main - undo button", () => {
  it("successful undo restores last swiped card", async () => {
    const { fetchSpy, undoButton } = await setupUndoTest()

    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: "undone" }),
    } as Response)

    await userEvent.click(undoButton)

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledTimes(3)
    })

    expect(screen.getByAltText("Movie 1")).toBeInTheDocument()
  })

  it("undo sends the correct POST request", async () => {
    const { deck, fetchSpy, undoButton } = await setupUndoTest()

    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: "undone" }),
    } as Response)

    await userEvent.click(undoButton)

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenNthCalledWith(
        3,
        expect.any(URL),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            media_id: deck[0].media_id
          })
        })
      )
    })

    const undoUrl = fetchSpy.mock.calls[2][0] as URL
    expect(undoUrl.href).toMatch(
      /\/room\/1234\/undo$/
    )
  })

  it("failed undo does not restore the card", async () => {
    const { deck, fetchSpy, undoButton } = await setupUndoTest()

    fetchSpy.mockResolvedValueOnce({
      ok: false,
    } as Response)

    await userEvent.click(undoButton)

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenNthCalledWith(
        3,
        expect.any(URL),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            media_id: deck[0].media_id
          })
        })
      )
    })

    const undoUrl = fetchSpy.mock.calls[2][0] as URL
    expect(undoUrl.href).toMatch(
      /\/room\/1234\/undo$/
    )    

    await waitFor(() => {
      expect(
        screen.queryByAltText("Movie 1")
      ).not.toBeInTheDocument()
    })
  })

  it("undo does nothing when there is no swipe history", async () => {
    const deck = makeDeck(3)
    const fetchSpy = vi.spyOn(globalThis, "fetch")
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {})

    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: async () => deck,
    } as Response)

    renderWithRoom(
      <SSEContextProvider>
        <Main />
      </SSEContextProvider>,
      { currentRoomCode: "1234", roomReady: true }
    )

    expect(await screen.findByAltText("Movie 1")).toBeInTheDocument()

    const undoButton = screen.getByRole("button", {
      name: /undo/i,
    })

    await userEvent.click(undoButton)

    expect(fetchSpy).toHaveBeenCalledTimes(1)

    expect(console.error)
      .toHaveBeenCalledWith(
        "Cannot undo without swipe history"
      )

    errSpy.mockRestore()
  })
})

describe("Main - genre change behavior", () => {
  const comedyDeck = Object.freeze([
    makeCard({
      media_id: "999",
      title: "Comedy Movie 1",
    }),
    makeCard({
      media_id: "888",
      title: "Comedy Movie 2",
    }),
    makeCard({
      media_id: "777",
      title: "Comedy Movie 3",
    }),
  ])

  it("sucessful POST changes genre and refreshes deck", async () => {
    const { user, fetchSpy } = await setupGenreChangeTest()

    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: async () => comedyDeck,
    } as Response)

    await user.click(
      screen.getByLabelText("Comedy")
    )

    await user.click(
      screen.getByRole("button", {
        name: /confirm/i,
      })
    )

    expect(await screen.findByAltText("Comedy Movie 1")).toBeInTheDocument()
    expect(screen.queryByAltText("Movie 1")).not.toBeInTheDocument()
    expect(screen.queryByText("Select Genre")).not.toBeInTheDocument()
  })

  it("does not refetch the deck when a local genre change is echoed by SSE", async () => {
    const user = userEvent.setup()
    const fetchSpy = vi.spyOn(globalThis, "fetch")
    const useSSESpy = vi.spyOn(useSSEModule, "useSSE")
    let sseState: {
      lastMessage: unknown
      error: string | null
      isConnected: boolean
    } = {
      lastMessage: null,
      error: null,
      isConnected: true,
    }

    useSSESpy.mockImplementation(() => sseState as ReturnType<typeof useSSEModule.useSSE>)

    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: async () => makeDeck(3),
    } as Response)

    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: async () => ["Action", "Comedy", "Drama"],
    } as Response)

    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: async () => comedyDeck,
    } as Response)

    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: async () => comedyDeck,
    } as Response)

    const roomContextValue = {
      currentRoomCode: "1234",
      setCurrentRoomCode: vi.fn(),
      roomReady: true,
      setRoomReady: vi.fn(),
      movies: true,
      setMovies: vi.fn(),
      tvShows: false,
      setTvShows: vi.fn(),
      isSoloMode: false,
      setIsSoloMode: vi.fn(),
      userInputCode: "",
      setUserInputCode: vi.fn(),
      genre: "Action",
      setGenre: vi.fn(),
      hideWatched: false,
      setHideWatched: vi.fn(),
    } as any

    const view = render(
      <RoomContext.Provider value={roomContextValue}>
        <SSEContextProvider>
          <Main />
        </SSEContextProvider>
      </RoomContext.Provider>,
    )

    expect(await screen.findByAltText("Movie 1")).toBeInTheDocument()

    await user.click(screen.getByText("Genres"))
    await user.click(screen.getByLabelText("Comedy"))
    await user.click(screen.getByRole("button", { name: /confirm/i }))

    expect(await screen.findByAltText("Comedy Movie 1")).toBeInTheDocument()

    sseState = {
      ...sseState,
      lastMessage: { event_type: "genre_changed", genre: "Comedy" },
    }

    view.rerender(
      <RoomContext.Provider value={roomContextValue}>
        <SSEContextProvider>
          <Main />
        </SSEContextProvider>
      </RoomContext.Provider>,
    )

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledTimes(3)
    })

    fetchSpy.mockRestore()
    useSSESpy.mockRestore()
  })

  it("failed POST does not change genre", async () => {
    const { user, fetchSpy } = await setupGenreChangeTest()

    fetchSpy.mockResolvedValueOnce({
      ok: false,
    } as Response)

    await user.click(
      screen.getByLabelText("Comedy")
    )

    await user.click(
      screen.getByRole("button", {
        name: /confirm/i,
      })
    )

    await waitFor(() => 
      expect(fetchSpy).toHaveBeenCalledTimes(3)
    )

    expect(screen.getByAltText("Movie 1")).toBeInTheDocument()
    expect(screen.queryByAltText("Comedy Movie 1")).not.toBeInTheDocument()
    expect(screen.getByText("Select Genre")).toBeInTheDocument()
  })

  it("POSTs with correct body and endpoint", async () => {
    const { user, fetchSpy } = await setupGenreChangeTest()

    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: async () => comedyDeck,
    } as Response)

    await user.click(
      screen.getByLabelText("Comedy")
    )

    await user.click(
      screen.getByRole("button", {
        name: /confirm/i,
      })
    )

    await waitFor(() => 
      expect(fetchSpy).toHaveBeenCalledTimes(3)
    )

    const [url, options] = fetchSpy.mock.calls[2]

    expect((url as URL).href).toMatch(/\/room\/1234\/genre$/)

    expect(
      JSON.parse(
        (options as RequestInit).body as string
      )
    ).toEqual({ genre: "Comedy", })
  })
})

describe("Main - watch filter toggle behavior", () => {
  const unwatchedDeck = Object.freeze([
    makeCard({
      media_id: "999",
      title: "Unwatched Movie 1",
    }),
    makeCard({
      media_id: "888",
      title: "Unwatched Movie 2",
    }),
    makeCard({
      media_id: "777",
      title: "Unwatched Movie 3",
    }),
  ])

  it("successful POST toggles watch filter and refreshes deck", async () => {
    const { user, fetchSpy, toggle } = await setupWatchedToggleTest()

    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: async () => unwatchedDeck,
    } as Response)

    await user.click(
      screen.getByTestId("watched-toggle")
    )

    expect(await screen.findByAltText("Unwatched Movie 1")).toBeInTheDocument()
    expect(screen.queryByAltText("Movie 1")).not.toBeInTheDocument()
    expect(toggle).toBeChecked()
  })

  it("does not refetch the deck when a local watched-filter change is echoed by SSE", async () => {
    const user = userEvent.setup()
    const fetchSpy = vi.spyOn(globalThis, "fetch")
    const useSSESpy = vi.spyOn(useSSEModule, "useSSE")
    let sseState: {
      lastMessage: unknown
      error: string | null
      isConnected: boolean
    } = {
      lastMessage: null,
      error: null,
      isConnected: true,
    }

    useSSESpy.mockImplementation(() => sseState as ReturnType<typeof useSSEModule.useSSE>)

    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: async () => makeDeck(3),
    } as Response)

    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: async () => unwatchedDeck,
    } as Response)

    const roomContextValue = {
      currentRoomCode: "1234",
      setCurrentRoomCode: vi.fn(),
      roomReady: true,
      setRoomReady: vi.fn(),
      movies: true,
      setMovies: vi.fn(),
      tvShows: false,
      setTvShows: vi.fn(),
      isSoloMode: false,
      setIsSoloMode: vi.fn(),
      userInputCode: "",
      setUserInputCode: vi.fn(),
      genre: "All",
      setGenre: vi.fn(),
      hideWatched: false,
      setHideWatched: vi.fn(),
    } as any

    const view = render(
      <RoomContext.Provider value={roomContextValue}>
        <SSEContextProvider>
          <Main />
        </SSEContextProvider>
      </RoomContext.Provider>,
    )

    expect(await screen.findByAltText("Movie 1")).toBeInTheDocument()

    await user.click(screen.getByTestId("watched-toggle"))

    expect(await screen.findByAltText("Unwatched Movie 1")).toBeInTheDocument()

    sseState = {
      ...sseState,
      lastMessage: { event_type: "hide_watched_changed", hide_watched: true },
    }

    view.rerender(
      <RoomContext.Provider value={roomContextValue}>
        <SSEContextProvider>
          <Main />
        </SSEContextProvider>
      </RoomContext.Provider>,
    )

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledTimes(2)
    })

    const [, options] = fetchSpy.mock.calls[1]
    expect((options as RequestInit).method).toBe("POST")
    expect(JSON.parse((options as RequestInit).body as string)).toEqual({
      hide_watched: true,
    })

    fetchSpy.mockRestore()
    useSSESpy.mockRestore()
  })

  it("failed POST leaves the deck and button state unchanged", async () => {
    const { user, fetchSpy, toggle } = await setupWatchedToggleTest()

    fetchSpy.mockResolvedValueOnce({
      ok: false,
    } as Response)

    await user.click(
      screen.getByTestId("watched-toggle")
    )

    expect(await screen.findByAltText("Movie 1")).toBeInTheDocument()
    expect(screen.queryByAltText("Unwatched Movie 1")).not.toBeInTheDocument()
    expect(toggle).not.toBeChecked()
  })

  it("POST sends the correct endpoint and body", async () => {
    const { user, fetchSpy } = await setupWatchedToggleTest()

    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: async () => unwatchedDeck,
    } as Response)

    await user.click(
      screen.getByTestId("watched-toggle")
    )

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledTimes(2)
    })

    const [url, options] = fetchSpy.mock.calls[1]

    expect((url as URL).href).toMatch(
      /\/room\/1234\/watched-filter$/
    )

    expect(
      JSON.parse((options as RequestInit).body as string)
    ).toEqual({
      hide_watched: true,
    })
  })
})


// LATER
// add test ID to top card: 
// data-testid={isTopCard ? "top-card" : undefined}

// then test:
// const topCard = screen.getByTestId("top-card")
// await swipeRight(topCard)
