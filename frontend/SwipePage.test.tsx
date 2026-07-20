// SwipePage.test.tsx — covers the swipe screen's derived rendering (the card
// stack and the left/right glow) and the end-session network action.
//
// Techniques in this file:
//   • makeDeck(n) from fixtures builds a deck with distinct titles, so we can
//     assert both the COUNT of rendered cards and their ORDER.
//   • The glow opacity is derived from `dragX`, and `dragX` only changes when
//     the top CardItemView's pointer handlers fire. jsdom can't do a real drag,
//     but test/setup.ts stubs the Pointer Capture methods so we can fire
//     pointerDown/pointerMove events and let the component compute opacity. We
//     take that route here (rather than skipping) because the glow MATH is the
//     real thing under test, and it works once the capture methods exist.
//   • mockFetch + the 3-part network contract for "End Session"
//     (request → success effect → one failure path).
//
// We deliberately do NOT test the static/dead elements (Undo, Shortlist, Show
// Watched, Genres, the hardcoded "Solo" mode-badge) — they have no wiring yet.

import { fireEvent, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { useState } from "react"
import SwipePage from "./SwipePage"
import { renderWithRoom, renderWithRoomStateful } from "./test/renderWithRoom"
import { mockFetch } from "./test/mockFetch"
import { makeDeck } from "./test/fixtures"
import { SSEContextProvider } from "./SSEContextProvider"
import { MatchItem } from "./types"

const DEFAULT_MATCHITEM: MatchItem = {
    title: null,
    thumb: null,
    media_id: null,
    media_type: null,
    deep_link: null,
    rating: null,
    duration: null,
    year: null
}

function renderSwipePage(deck: number = 2, roomReadyState: boolean = true, showGenreModalState: boolean = false) {
  const utils = renderWithRoom(
    <SSEContextProvider>
      <SwipePage 
        cardDeck={makeDeck(deck)} 
        matchFound={false} 
        handleMatchClose={vi.fn()} 
        matchItem={DEFAULT_MATCHITEM}
        handleUndo={vi.fn()}
        handleGenreChange={vi.fn()}
        showGenreModal={showGenreModalState}
        setShowGenreModal={vi.fn()}
        handleWatchedFilterToggle={vi.fn()}
      />
    </SSEContextProvider>,
    { currentRoomCode: "1234", roomReady: roomReadyState }
  )

  return {
    ...utils,
  }
}

describe("SwipePage - HostWaiting rendering logic", () => {
  it("renders only HostWaiting when roomReady is false", async () => {
    mockFetch({ ok: true, body: [] })
    renderSwipePage(2, false)

    expect(
      screen.queryByText("Waiting for partner...")
    ).toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: /show watched/i })
    ).not.toBeInTheDocument
  })

  it("does not render HostWaiting and renders the rest of SwipePage when roomReady is true", async () => {
    mockFetch({ ok: true, body: [] })
    renderSwipePage()

    expect(
      screen.queryByRole("button", { name: /show watched/i })
    ).toBeInTheDocument
    expect(
      screen.queryByText("Waiting for partner...")
    ).not.toBeInTheDocument()
  })
})

describe("SwipePage — card-stack slicing", () => {
  it("renders at most 5 cards (visibleCards = deck.slice(0,5)) in reverse order", () => {
    const { container } = renderSwipePage(7)
    const cards = container.querySelectorAll(".card-item-container")
    // 7 in the deck, but only the first 5 are visible.
    expect(cards).toHaveLength(5);

    // visibleCards is `slice(0,5).reverse()`, so DOM order is Movie 5..Movie 1.
    const titles = Array.from(cards).map(
      (c) => c.querySelector(".card-item-title")?.textContent,
    )
    expect(titles).toEqual([
      "Movie 5",
      "Movie 4",
      "Movie 3",
      "Movie 2",
      "Movie 1",
    ])
  })

  it("renders every card when the deck is smaller than 5", () => {
    const { container } = renderSwipePage(3)
    expect(container.querySelectorAll(".card-item-container")).toHaveLength(3)
  })
})

describe("SwipePage — glow opacity", () => {
  it("has zero glow opacity at rest (dragX === 0)", () => {
    const { container } = renderSwipePage()
    const left = container.querySelector(".glow-left") as HTMLElement
    const right = container.querySelector(".glow-right") as HTMLElement
    expect(left.style.opacity).toBe("0")
    expect(right.style.opacity).toBe("0")
  })

  it("clamps right-glow opacity to 1 once dragged well past the threshold", () => {
    const { container } = renderSwipePage()

    // The top card is the LAST rendered container (isTopCard === true), and is
    // the only one with pointer handlers attached.
    const cards = container.querySelectorAll(".card-item-container")
    const topCard = cards[cards.length - 1]

    // Simulate a rightward drag of 250px: start at 0, move to 250.
    // rightOpacity = min(|250|/200, 1) = 1.
    fireEvent.pointerDown(topCard, { clientX: 0, pointerId: 1 })
    fireEvent.pointerMove(topCard, { clientX: 250, pointerId: 1 })

    const right = container.querySelector(".glow-right") as HTMLElement
    const left = container.querySelector(".glow-left") as HTMLElement
    expect(right.style.opacity).toBe("1")
    expect(left.style.opacity).toBe("0")
  })

  it("clamps left-glow opacity to 1 once dragged well past the threshold", () => {
    const { container } = renderSwipePage()
    // The top card is the LAST rendered container (isTopCard === true), and is
    // the only one with pointer handlers attached.
    const cards = container.querySelectorAll(".card-item-container")
    const topCard = cards[cards.length - 1]

    // Simulate a leftward drag of 250px: start at 0, move to -250.
    // leftOpacity = min(|250|/200, 1) = 1.
    fireEvent.pointerDown(topCard, { clientX: 0, pointerId: 1 })
    fireEvent.pointerMove(topCard, { clientX: -250, pointerId: 1 })

    const right = container.querySelector(".glow-right") as HTMLElement
    const left = container.querySelector(".glow-left") as HTMLElement
    expect(left.style.opacity).toBe("1")
    expect(right.style.opacity).toBe("0")
  })

  it("keeps glow at 0 at the exact threshold boundary (dragX === 20)", () => {
    const { container } = renderSwipePage()
    const cards = container.querySelectorAll(".card-item-container")
    const topCard = cards[cards.length - 1]

    // dragX === 20 is NOT > 20, so the glow stays off (strict inequality).
    fireEvent.pointerDown(topCard, { clientX: 0, pointerId: 1 })
    fireEvent.pointerMove(topCard, { clientX: 20, pointerId: 1 })

    const right = container.querySelector(".glow-right") as HTMLElement;
    expect(right.style.opacity).toBe("0")
  })
})

describe("SwipePage — end session (3-part network contract)", () => {
  it("POSTs to /room/{code}/quit, then clears the room code on success", async () => {
    const spy = mockFetch({ ok: true, body: { pairing_code: "1234" } })
    const { ctx } = renderSwipePage()

    fireEvent.click(screen.getByText("End Session"))

    // 1. The request: correct URL (.href on the URL object) + method.
    await waitFor(() => expect(spy).toHaveBeenCalledTimes(1))
    const [url, options] = spy.mock.calls[0]
    expect((url as URL).href).toMatch(/\/room\/1234\/quit$/)
    expect((options as RequestInit).method).toBe("POST")

    // 2. The success effect: setCurrentRoomCode(null).
    await waitFor(() => expect(ctx.setCurrentRoomCode).toHaveBeenCalledWith(null))
  })

  it("leaves the room code untouched when quit responds non-ok", async () => {
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {})
    const spy = mockFetch({ ok: false })
    const { ctx } = renderSwipePage()

    fireEvent.click(screen.getByText("End Session"))

    await waitFor(() => expect(spy).toHaveBeenCalled())
    expect(ctx.setCurrentRoomCode).not.toHaveBeenCalled()

    errSpy.mockRestore()    
  })

  it("leaves the room code untouched and does not throw when the request fails", async () => {
    // Silence the expected console.error so the failure path stays quiet.
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {})
    const spy = mockFetch({ reject: true })
    const { ctx } = renderSwipePage()

    fireEvent.click(screen.getByText("End Session"))

    // 3. The failure path: the request was attempted, but the success effect
    // never runs and nothing throws.
    await waitFor(() => expect(spy).toHaveBeenCalled())
    expect(ctx.setCurrentRoomCode).not.toHaveBeenCalled()

    errSpy.mockRestore()
  })
})

function GenreModalHarness() {
  const [showGenreModal, setShowGenreModal] = useState(false)

  return (
    <SSEContextProvider>
      <SwipePage
        cardDeck={makeDeck(2)}
        matchFound={false}
        handleMatchClose={vi.fn()}
        matchItem={DEFAULT_MATCHITEM}
        handleUndo={vi.fn()}
        handleGenreChange={vi.fn()}
        showGenreModal={showGenreModal}
        setShowGenreModal={setShowGenreModal}
        handleWatchedFilterToggle={vi.fn()}
      />
    </SSEContextProvider>
  )
}

describe("SwipePage - GenreModal behavior", () => {
  it("does not render GenreModal when showGenreModal is false", () => {
    renderSwipePage()
    expect(
      screen.queryByText("Select Genre")
    ).not.toBeInTheDocument()
  })

  it("renders GenreModal when showGenreModal is true", () => {
    renderSwipePage(2, true, true)
    expect(
      screen.queryByText("Select Genre")
    ).toBeInTheDocument()
  })

  it("clicking on genres toggles showGenreModal", async () => {
    const user = userEvent.setup()

    renderWithRoomStateful(<GenreModalHarness />,
      { currentRoomCode: "1234", roomReady: true }
    )

    const genresButton = screen.getByRole("button", {
      name: /genres/i,
    })

    expect(
      screen.queryByText("Select Genre")
    ).not.toBeInTheDocument()

    await user.click(genresButton)

    expect(
      screen.queryByText("Select Genre")
    ).toBeInTheDocument()
  })
})
