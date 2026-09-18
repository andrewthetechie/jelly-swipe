import { fireEvent, screen, waitFor } from "@testing-library/react"
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
  postSwipe: vi.fn(),
  fetchDeck: vi.fn(),
  fetchGenres: vi.fn(),
  fetchMatches: vi.fn(),
}))

const quitRoomMock = vi.mocked(roomApi.quitRoom)
const postSwipeMock = vi.mocked(roomApi.postSwipe)
const fetchDeckMock = vi.mocked(roomApi.fetchDeck)
const fetchGenresMock = vi.mocked(roomApi.fetchGenres)
const fetchMatchesMock = vi.mocked(roomApi.fetchMatches)

beforeEach(() => {
  vi.clearAllMocks()
  quitRoomMock.mockResolvedValue({ status: "ok" })
  postSwipeMock.mockResolvedValue(undefined)
  fetchDeckMock.mockResolvedValue([])
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

const topCardTransformX = (top: HTMLElement): number =>
  parseFloat(top.style.transform.match(/translate\((-?[\d.]+)px/)?.[1] ?? "0")

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

describe("SwipePage — end of deck", () => {
  it("shows an explanatory end-of-deck state once a completed load yields an empty deck", async () => {
    renderSwipePage(0)

    expect(await screen.findByText("That's everything for these filters.")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /open matches/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /change genre/i })).toBeInTheDocument()
  })

  it("does not show the end-of-deck message while the initial deck fetch is in flight", () => {
    // A never-resolving fetch keeps deckLoaded false (load incomplete).
    fetchDeckMock.mockImplementation(() => new Promise<never>(() => {}))

    renderSwipePageWithError(null, {
      cardDeck: [],
      deckLoaded: false,
    })

    expect(screen.queryByText("That's everything for these filters.")).not.toBeInTheDocument()
  })

  it("keeps the deck-error retry panel taking precedence over the end-of-deck message", async () => {
    renderSwipePageWithError(null, {
      cardDeck: [],
      deckError: "Couldn't load your cards. Check your connection and try again.",
      deckLoaded: true,
    })

    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't load your cards. Check your connection and try again.")
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument()
    expect(screen.queryByText("That's everything for these filters.")).not.toBeInTheDocument()
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

  it("opens MatchListModal from the Matches button and closes it on Escape", async () => {
    const user = userEvent.setup()
    renderSwipePage()

    expect(screen.queryByRole("dialog", { name: /matches/i })).not.toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: /matches/i }))
    expect(screen.getByRole("dialog", { name: /matches/i })).toBeInTheDocument()

    await user.keyboard("{Escape}")
    expect(screen.queryByRole("dialog", { name: /matches/i })).not.toBeInTheDocument()
  })

  it("opens MatchListModal from the Matches button and closes it on overlay click", async () => {
    const user = userEvent.setup()
    renderSwipePage()

    await user.click(screen.getByRole("button", { name: /matches/i }))
    expect(screen.getByRole("dialog", { name: /matches/i })).toBeInTheDocument()

    await user.click(screen.getByRole("dialog"))
    expect(screen.queryByRole("dialog", { name: /matches/i })).not.toBeInTheDocument()
  })
})

describe("SwipePage — Nope/Like buttons (issue #344)", () => {
  it("renders Nope, Undo, and Like under the deck in that order", () => {
    const { container } = renderSwipePage()
    const controls = container.querySelector(".swipe-controls") as HTMLElement
    const labels = Array.from(controls.querySelectorAll("button")).map(
      (b) => b.textContent?.trim(),
    )
    expect(labels).toEqual(["✕Nope", "Undo", "✓Like"])
  })

  it("commits a right swipe on the top card when Like is clicked", async () => {
    const user = userEvent.setup()
    const { container } = renderSwipePage(2)
    const cards = container.querySelectorAll(".card-item-container")
    const topCard = cards[cards.length - 1] as HTMLElement

    await user.click(screen.getByRole("button", { name: /like/i }))

    // Routed through the same swipe path a gesture uses (top card, right).
    expect(postSwipeMock).toHaveBeenCalledWith("1234", "1", "right")

    // Same exit transform as a drag commit: the top card flies off-screen.
    expect(Math.abs(topCardTransformX(topCard))).toBeGreaterThan(500)
  })

  it("commits a left swipe on the top card when Nope is clicked", async () => {
    const user = userEvent.setup()
    const { container } = renderSwipePage(2)
    const cards = container.querySelectorAll(".card-item-container")
    const topCard = cards[cards.length - 1] as HTMLElement

    await user.click(screen.getByRole("button", { name: /nope/i }))

    expect(postSwipeMock).toHaveBeenCalledWith("1234", "1", "left")

    expect(Math.abs(topCardTransformX(topCard))).toBeGreaterThan(500)
  })

  it("disables both buttons and posts nothing when the deck is empty", async () => {
    const user = userEvent.setup()
    renderSwipePage(0)

    const likeButton = screen.getByRole("button", { name: /like/i })
    const nopeButton = screen.getByRole("button", { name: /nope/i })

    expect(likeButton).toBeDisabled()
    expect(nopeButton).toBeDisabled()

    await user.click(likeButton)
    await user.click(nopeButton)

    expect(postSwipeMock).not.toHaveBeenCalled()
  })

  it("shows a dismissible error banner, keeps the card retryable when a swipe POST rejects", async () => {
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {})
    const user = userEvent.setup()
    postSwipeMock.mockRejectedValue(new Error("swipe failed"))
    const { container } = renderSwipePage(2)
    const cards = container.querySelectorAll(".card-item-container")
    const topCard = cards[cards.length - 1] as HTMLElement

    await user.click(screen.getByRole("button", { name: /like/i }))

    await waitFor(() => expect(postSwipeMock).toHaveBeenCalled())
    const banner = screen.getByRole("alert")
    expect(banner).toHaveTextContent("Couldn't save that swipe. Check your connection and try again.")

    // The swiped card is NOT removed on failure.
    expect(container.querySelectorAll(".card-item-container")).toHaveLength(2)
    expect(screen.getByText("Movie 1")).toBeInTheDocument()

    // The top card snaps back to its resting transform so it can be re-swiped.
    await waitFor(() => expect(topCard.style.transform).toContain("translate(0px, 0px)"))

    // A second Like click retries the same swipe.
    await user.click(screen.getByRole("button", { name: /like/i }))
    await waitFor(() => expect(postSwipeMock).toHaveBeenCalledTimes(2))
    expect(postSwipeMock).toHaveBeenLastCalledWith("1234", "1", "right")

    await user.click(screen.getByRole("button", { name: "Dismiss error" }))
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()

    errSpy.mockRestore()
  })
})

describe("SwipePage — keyboard swipe and flip (issue #344)", () => {
  const topCard = (container: HTMLElement): HTMLElement => {
    const cards = container.querySelectorAll(".card-item-container")
    return cards[cards.length - 1] as HTMLElement
  }

  it("commits a right swipe on the top card with ArrowRight", () => {
    const { container } = renderSwipePage(2)
    const card = topCard(container)

    fireEvent.keyDown(window, { key: "ArrowRight" })

    expect(postSwipeMock).toHaveBeenCalledWith("1234", "1", "right")
    expect(Math.abs(topCardTransformX(card))).toBeGreaterThan(500)
  })

  it("commits a left swipe on the top card with ArrowLeft", () => {
    const { container } = renderSwipePage(2)
    const card = topCard(container)

    fireEvent.keyDown(window, { key: "ArrowLeft" })

    expect(postSwipeMock).toHaveBeenCalledWith("1234", "1", "left")
    expect(Math.abs(topCardTransformX(card))).toBeGreaterThan(500)
  })

  it("flips the top card details with ArrowUp", () => {
    const { container } = renderSwipePage(2)

    fireEvent.keyDown(window, { key: "ArrowUp" })

    expect(topCard(container)).toHaveClass("flipped")
    expect(postSwipeMock).not.toHaveBeenCalled()
  })

  it("flips the top card details with Enter", () => {
    const { container } = renderSwipePage(2)

    fireEvent.keyDown(window, { key: "Enter" })

    expect(topCard(container)).toHaveClass("flipped")
    expect(postSwipeMock).not.toHaveBeenCalled()
  })

  it("does nothing when focus is on an interactive element", () => {
    const { container } = renderSwipePage(2)
    const checkbox = screen.getByRole("checkbox", { name: /hide watched/i })
    checkbox.focus()

    fireEvent.keyDown(window, { key: "ArrowLeft" })
    fireEvent.keyDown(window, { key: "ArrowRight" })
    fireEvent.keyDown(window, { key: "ArrowUp" })
    fireEvent.keyDown(window, { key: "Enter" })

    expect(postSwipeMock).not.toHaveBeenCalled()
    expect(topCard(container)).not.toHaveClass("flipped")
  })

  it("does nothing while the GenreModal is open", async () => {
    const user = userEvent.setup()
    const { container } = renderSwipePage(2)

    await user.click(screen.getByRole("button", { name: /genres/i }))
    ;(document.activeElement as HTMLElement)?.blur()

    fireEvent.keyDown(window, { key: "ArrowLeft" })
    fireEvent.keyDown(window, { key: "ArrowRight" })
    fireEvent.keyDown(window, { key: "ArrowUp" })
    fireEvent.keyDown(window, { key: "Enter" })

    expect(postSwipeMock).not.toHaveBeenCalled()
    expect(topCard(container)).not.toHaveClass("flipped")
  })

  it("does nothing while the MatchListModal is open", async () => {
    const user = userEvent.setup()
    const { container } = renderSwipePage(2)

    await user.click(screen.getByRole("button", { name: /matches/i }))
    ;(document.activeElement as HTMLElement)?.blur()

    fireEvent.keyDown(window, { key: "ArrowLeft" })
    fireEvent.keyDown(window, { key: "ArrowRight" })
    fireEvent.keyDown(window, { key: "ArrowUp" })
    fireEvent.keyDown(window, { key: "Enter" })

    expect(postSwipeMock).not.toHaveBeenCalled()
    expect(topCard(container)).not.toHaveClass("flipped")
  })

  it("does nothing while the MatchFound modal is open", () => {
    const { container } = renderSwipePageWithError(null, { matchFound: true })

    fireEvent.keyDown(window, { key: "ArrowLeft" })
    fireEvent.keyDown(window, { key: "ArrowRight" })
    fireEvent.keyDown(window, { key: "ArrowUp" })
    fireEvent.keyDown(window, { key: "Enter" })

    expect(postSwipeMock).not.toHaveBeenCalled()
    expect(topCard(container)).not.toHaveClass("flipped")
  })

  it("ignores key-repeat events", () => {
    const { container } = renderSwipePage(2)

    fireEvent.keyDown(window, { key: "ArrowLeft", repeat: true })
    fireEvent.keyDown(window, { key: "ArrowRight", repeat: true })
    fireEvent.keyDown(window, { key: "ArrowUp", repeat: true })
    fireEvent.keyDown(window, { key: "Enter", repeat: true })

    expect(postSwipeMock).not.toHaveBeenCalled()
    expect(topCard(container)).not.toHaveClass("flipped")
  })

  it("mentions the arrow keys in the card-item-instructions hint", () => {
    renderSwipePage()
    expect(screen.getByText("Tap for details · Arrow keys to swipe")).toBeInTheDocument()
  })

  it("shows a dismissible error banner and keeps the card retryable when a keyboard swipe rejects", async () => {
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {})
    postSwipeMock.mockRejectedValueOnce(new Error("swipe failed"))
    const { container } = renderSwipePage(2)
    const cards = container.querySelectorAll(".card-item-container")
    const topCard = cards[cards.length - 1] as HTMLElement

    fireEvent.keyDown(window, { key: "ArrowRight" })

    await waitFor(() => expect(postSwipeMock).toHaveBeenCalled())
    const banner = screen.getByRole("alert")
    expect(banner).toHaveTextContent("Couldn't save that swipe. Check your connection and try again.")

    expect(container.querySelectorAll(".card-item-container")).toHaveLength(2)
    expect(screen.getByText("Movie 1")).toBeInTheDocument()

    // The top card snaps back to its resting transform so it can be re-swiped.
    await waitFor(() => expect(topCard.style.transform).toContain("translate(0px, 0px)"))

    // A second ArrowRight retries the same swipe.
    fireEvent.keyDown(window, { key: "ArrowRight" })
    await waitFor(() => expect(postSwipeMock).toHaveBeenCalledTimes(2))
    expect(postSwipeMock).toHaveBeenLastCalledWith("1234", "1", "right")

    errSpy.mockRestore()
  })
})
