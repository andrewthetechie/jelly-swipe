import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import SwipePage from "./SwipePage"
import { renderWithRoom, renderWithRoomStateful } from "./test/renderWithRoom"
import { makeDeck, dragTo, cancelDrag } from "./test/fixtures"
import * as roomApi from "./roomApi"

function getRoomState() {
  return JSON.parse(screen.getByTestId("room-state").textContent ?? "{}");
}

vi.mock("./roomApi", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./roomApi")>()),
  quitRoom: vi.fn(),
  fetchDeck: vi.fn(),
  fetchGenres: vi.fn(),
  fetchMatches: vi.fn(),
}))

const quitRoomMock = vi.mocked(roomApi.quitRoom)
const fetchGenresMock = vi.mocked(roomApi.fetchGenres)
const fetchMatchesMock = vi.mocked(roomApi.fetchMatches)

beforeEach(() => {
  vi.clearAllMocks()
  quitRoomMock.mockResolvedValue({ status: "ok" })
  fetchGenresMock.mockResolvedValue(["Action", "Comedy", "Drama"])
  fetchMatchesMock.mockResolvedValue([])
})

function renderSwipePage(
  deckSize = 2,
  roomReadyState = true,
) {
  return renderWithRoom(<SwipePage />, {
    currentRoomCode: "1234",
    roomReady: roomReadyState,
    cardDeck: makeDeck(deckSize),
    matchFound: false,
  })
}

function renderSwipePageWithError(
  lastError: string | null = null,
  overrides: Parameters<typeof renderWithRoom>[1] = {},
) {
  return renderWithRoom(<SwipePage />, {
    currentRoomCode: "1234",
    roomReady: true,
    cardDeck: makeDeck(2),
    matchFound: false,
    lastError,
    ...overrides,
  })
}

describe("SwipePage - HostWaiting rendering logic", () => {
  it("renders only HostWaiting when roomReady is false", () => {
    renderSwipePage(2, false)

    expect(screen.queryByText("Waiting for partner...")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /hide watched/i })).not.toBeInTheDocument()
  })

  it("does not render HostWaiting and renders the rest of SwipePage when roomReady is true", () => {
    renderSwipePage()

    expect(screen.queryByRole("checkbox", { name: /hide watched/i })).toBeInTheDocument()
    expect(screen.queryByText("Waiting for partner...")).not.toBeInTheDocument()
  })
})

describe("SwipePage — card-stack slicing", () => {
  it("renders at most 3 cards (visibleCards = deck.slice(0,3)) in reverse order", () => {
    const { container } = renderSwipePage(7)
    const cards = container.querySelectorAll(".card-item-container")
    expect(cards).toHaveLength(3)

    const titles = Array.from(cards).map(
      (c) => c.querySelector(".card-item-title")?.textContent,
    )
    expect(titles).toEqual([
      "Movie 3",
      "Movie 2",
      "Movie 1",
    ])
  })

  it("renders every card when the deck is smaller than 3", () => {
    const { container } = renderSwipePage(2)
    expect(container.querySelectorAll(".card-item-container")).toHaveLength(2)
  })
})

describe("SwipePage — card-stack depth (issue #343)", () => {
  it("marks only the top card as interactive and the back cards as dimmed stack", () => {
    const { container } = renderSwipePage(7)
    const cards = Array.from(container.querySelectorAll(".card-item-container"))
    // Rendered reversed: index 0 is deepest (stackIndex 2), last is top (stackIndex 0).
    expect(cards).toHaveLength(3)

    const top = cards[2] as HTMLElement
    const mid = cards[1] as HTMLElement
    const deep = cards[0] as HTMLElement

    // Top card: interactive, full shadow, no dim/stack class.
    expect(top.style.pointerEvents).toBe("auto")
    expect(top).not.toHaveClass("stack-back")
    expect(top.style.filter).toBe("")

    // Back cards: non-interactive and stacked.
    expect(mid.style.pointerEvents).toBe("none")
    expect(deep.style.pointerEvents).toBe("none")
    expect(mid).toHaveClass("stack-back")
    expect(deep).toHaveClass("stack-back")
  })

  it("orders back-card transforms and brightness by depth", () => {
    // Assert the ordering pattern (deeper = more offset, less scale, less brightness),
    // not exact pixel values — those may be fine-tuned without breaking the intent.
    // Back cards are pushed *up* out of the top card's outline, so the offset
    // is a negative percentage; deeper cards sit further up.
    const parseTranslateY = (transform: string) =>
      parseFloat(transform.match(/translateY\(([^%]+)%\)/)?.[1] ?? "0")
    const parseScale = (transform: string) =>
      parseFloat(transform.match(/scale\(([^)]+)\)/)?.[1] ?? "1")
    const parseBrightness = (filter: string) =>
      parseFloat(filter.match(/brightness\(([^)]+)\)/)?.[1] ?? "1")

    const { container } = renderSwipePage(7)
    const cards = Array.from(container.querySelectorAll(".card-item-container")) as HTMLElement[]
    // cards[0] = stackIndex 2 (deepest), cards[1] = stackIndex 1, cards[2] = stackIndex 0 (top).

    const deep = cards[0]
    const mid = cards[1]
    const top = cards[2]

    // Top card has no stack offset/filter.
    expect(top.style.transform).not.toContain("translateY")
    expect(top.style.filter).toBe("")

    // Offset grows with depth (further up, so more negative).
    expect(parseTranslateY(mid.style.transform)).toBeLessThan(0)
    expect(parseTranslateY(deep.style.transform)).toBeLessThan(parseTranslateY(mid.style.transform))

    // Scale shrinks with depth.
    expect(parseScale(mid.style.transform)).toBeLessThan(1)
    expect(parseScale(deep.style.transform)).toBeLessThan(parseScale(mid.style.transform))

    // Brightness dims with depth.
    expect(parseBrightness(mid.style.filter)).toBeLessThan(1)
    expect(parseBrightness(deep.style.filter)).toBeLessThan(parseBrightness(mid.style.filter))
  })

  it("renders a single-card deck as just a top card with no phantom stack", () => {
    const { container } = renderSwipePage(1)
    const cards = container.querySelectorAll(".card-item-container")
    expect(cards).toHaveLength(1)
    expect(cards[0]).not.toHaveClass("stack-back")
  })
})

describe("SwipePage — swipe verdict feedback", () => {
  it("has both stamps at opacity 0 at rest", () => {
    const { container } = renderSwipePage()
    const cards = container.querySelectorAll(".card-item-container")
    const topCard = cards[cards.length - 1] as HTMLElement
    expect((topCard.querySelector(".swipe-stamp-like") as HTMLElement).style.opacity).toBe("0")
    expect((topCard.querySelector(".swipe-stamp-nope") as HTMLElement).style.opacity).toBe("0")
  })

  it("lights LIKE on the top card when dragged well past the threshold", () => {
    const { container } = renderSwipePage()
    const cards = container.querySelectorAll(".card-item-container")
    const topCard = cards[cards.length - 1] as HTMLElement
    dragTo(topCard, 250)
    expect((topCard.querySelector(".swipe-stamp-like") as HTMLElement).style.opacity).toBe("1")
    expect((topCard.querySelector(".swipe-stamp-nope") as HTMLElement).style.opacity).toBe("0")
  })

  it("lights NOPE on the top card when dragged left past the threshold", () => {
    const { container } = renderSwipePage()
    const cards = container.querySelectorAll(".card-item-container")
    const topCard = cards[cards.length - 1] as HTMLElement
    dragTo(topCard, -250)
    expect((topCard.querySelector(".swipe-stamp-nope") as HTMLElement).style.opacity).toBe("1")
    expect((topCard.querySelector(".swipe-stamp-like") as HTMLElement).style.opacity).toBe("0")
  })

  it("keeps both stamps at 0 inside the dead zone (clientX === 10)", () => {
    const { container } = renderSwipePage()
    const cards = container.querySelectorAll(".card-item-container")
    const topCard = cards[cards.length - 1] as HTMLElement
    dragTo(topCard, 10)
    expect((topCard.querySelector(".swipe-stamp-like") as HTMLElement).style.opacity).toBe("0")
    expect((topCard.querySelector(".swipe-stamp-nope") as HTMLElement).style.opacity).toBe("0")
  })

  it("renders verdict feedback only on the top card (3-card deck)", () => {
    const { container } = renderSwipePage(3)
    // Two stamps (like + nope), both on the top card only.
    expect(container.querySelectorAll(".swipe-stamp")).toHaveLength(2)
  })

  it("clears both stamps when a live drag is cancelled", () => {
    const { container } = renderSwipePage()
    const cards = container.querySelectorAll(".card-item-container")
    const topCard = cards[cards.length - 1] as HTMLElement
    dragTo(topCard, 250)
    cancelDrag(topCard)
    expect((topCard.querySelector(".swipe-stamp-like") as HTMLElement).style.opacity).toBe("0")
    expect((topCard.querySelector(".swipe-stamp-nope") as HTMLElement).style.opacity).toBe("0")
  })
})

describe("SwipePage — end session command", () => {
  it("calls roomApi.quitRoom with current room code and clears room code on success", async () => {
    const user = userEvent.setup()
    renderSwipePage()

    await user.click(screen.getByText("End Session"))

    await waitFor(() => expect(quitRoomMock).toHaveBeenCalledTimes(1))
    expect(quitRoomMock).toHaveBeenCalledWith("1234")
    await waitFor(() => expect(getRoomState()).toMatchObject({ currentRoomCode: null }))
  })

  it("leaves the room code untouched when quit rejects", async () => {
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {})
    const user = userEvent.setup()
    quitRoomMock.mockRejectedValueOnce(new Error("quit failed"))
    renderSwipePage()

    await user.click(screen.getByText("End Session"))

    await waitFor(() => expect(quitRoomMock).toHaveBeenCalled())
    expect(getRoomState()).toMatchObject({ currentRoomCode: "1234" })

    errSpy.mockRestore()
  })
})

describe("SwipePage — error banner (issue #340)", () => {
  it("renders a seeded lastError as a dismissible banner with role=alert", async () => {
    const user = userEvent.setup()
    renderSwipePageWithError("Couldn't save that swipe. Check your connection and try again.")

    const banner = screen.getByRole("alert")
    expect(banner).toHaveTextContent("Couldn't save that swipe. Check your connection and try again.")

    await user.click(screen.getByRole("button", { name: "Dismiss error" }))
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
  })

  it("does not render an error banner when lastError is null", () => {
    renderSwipePage()
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
  })

  it("shows a dismissible end-session error banner on the HostWaiting screen when quit rejects", async () => {
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {})
    const user = userEvent.setup()
    quitRoomMock.mockRejectedValueOnce(new Error("quit failed"))
    renderSwipePageWithError(null, { roomReady: false })

    await user.click(screen.getByText("End Session"))

    await waitFor(() => expect(quitRoomMock).toHaveBeenCalled())
    const banner = screen.getByRole("alert")
    expect(banner).toHaveTextContent("Couldn't end the session. Check your connection and try again.")

    await user.click(screen.getByRole("button", { name: "Dismiss error" }))
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()

    errSpy.mockRestore()
  })
})

describe("SwipePage — deck error retry (issue #340)", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    quitRoomMock.mockResolvedValue({ status: "ok" })
  })

  it("shows the deck-error message and a Try again button instead of a blank deck", async () => {
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {})
    const fetchDeckMock = vi.mocked(roomApi.fetchDeck)
    fetchDeckMock.mockRejectedValue(new Error("fetch failed"))

    renderSwipePageWithError(null, {
      cardDeck: [],
      deckError: "Couldn't load your cards. Check your connection and try again.",
    })

    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't load your cards. Check your connection and try again.")
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument()
    expect(screen.queryByText("Movie 1")).not.toBeInTheDocument()

    errSpy.mockRestore()
  })

  it("keeps the loaded deck visible when a deck error is set (transient refetch failure)", () => {
    renderSwipePageWithError(null, {
      cardDeck: makeDeck(2),
      deckError: "Couldn't load your cards. Check your connection and try again.",
    })

    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
    expect(screen.getByText("Movie 1")).toBeInTheDocument()
  })

  it("retries the deck fetch and clears deckError on success", async () => {
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {})
    const fetchDeckMock = vi.mocked(roomApi.fetchDeck)
    fetchDeckMock.mockRejectedValueOnce(new Error("fetch failed"))
    fetchDeckMock.mockResolvedValue(makeDeck(2))

    const user = userEvent.setup()
    renderSwipePageWithError(null, {
      cardDeck: [],
      deckError: "Couldn't load your cards. Check your connection and try again.",
    })

    await user.click(await screen.findByRole("button", { name: "Try again" }))

    await waitFor(() => expect(fetchDeckMock).toHaveBeenCalledWith("1234"))
    expect(await screen.findByText("Movie 1")).toBeInTheDocument()
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()

    errSpy.mockRestore()
  })
})

describe("SwipePage - GenreModal behavior", () => {
  it("does not render GenreModal initially", () => {
    renderSwipePage()
    expect(screen.queryByText("Select Genre")).not.toBeInTheDocument()
  })

  it("renders GenreModal after clicking the Genres button", async () => {
    const user = userEvent.setup()

    renderWithRoomStateful(<SwipePage />, {
      currentRoomCode: "1234",
      roomReady: true,
      cardDeck: makeDeck(2),
      matchFound: false,
    })

    await user.click(screen.getByRole("button", { name: /genres/i }))

    expect(screen.queryByText("Select Genre")).toBeInTheDocument()
  })

  it("opens GenreModal from the Genres button and closes it on Escape", async () => {
    const user = userEvent.setup()
    renderSwipePage()

    expect(screen.queryByText("Select Genre")).not.toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: /genres/i }))
    expect(screen.getByRole("dialog", { name: /select genre/i })).toBeInTheDocument()

    await user.keyboard("{Escape}")
    expect(screen.queryByText("Select Genre")).not.toBeInTheDocument()
  })

  it("opens GenreModal from the Genres button and closes it on overlay click", async () => {
    const user = userEvent.setup()
    renderSwipePage()

    await user.click(screen.getByRole("button", { name: /genres/i }))
    expect(screen.getByRole("dialog", { name: /select genre/i })).toBeInTheDocument()

    await user.click(screen.getByRole("dialog"))
    expect(screen.queryByText("Select Genre")).not.toBeInTheDocument()
  })

  it("opens MatchListModal from the Shortlist button and closes it on Escape", async () => {
    const user = userEvent.setup()
    renderSwipePage()

    expect(screen.queryByText("Match List")).not.toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: /shortlist/i }))
    expect(screen.getByRole("dialog", { name: /match list/i })).toBeInTheDocument()

    await user.keyboard("{Escape}")
    expect(screen.queryByText("Match List")).not.toBeInTheDocument()
  })

  it("opens MatchListModal from the Shortlist button and closes it on overlay click", async () => {
    const user = userEvent.setup()
    renderSwipePage()

    await user.click(screen.getByRole("button", { name: /shortlist/i }))
    expect(screen.getByRole("dialog", { name: /match list/i })).toBeInTheDocument()

    await user.click(screen.getByRole("dialog"))
    expect(screen.queryByText("Match List")).not.toBeInTheDocument()
  })
})
