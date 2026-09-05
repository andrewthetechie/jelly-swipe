import { fireEvent, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import SwipePage from "./SwipePage"
import { renderWithRoom, renderWithRoomStateful } from "./test/renderWithRoom"
import { makeDeck } from "./test/fixtures"
import * as roomApi from "./roomApi"

function getRoomState() {
  return JSON.parse(screen.getByTestId("room-state").textContent ?? "{}");
}

vi.mock("./roomApi", () => ({
  quitRoom: vi.fn(),
}))

const quitRoomMock = vi.mocked(roomApi.quitRoom)

beforeEach(() => {
  vi.clearAllMocks()
  quitRoomMock.mockResolvedValue({ status: "ok" })
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
    const { container } = renderSwipePage(7)
    const cards = Array.from(container.querySelectorAll(".card-item-container")) as HTMLElement[]
    // cards[0] = stackIndex 2, cards[1] = stackIndex 1, cards[2] = stackIndex 0.
    expect(cards[0].style.transform).toContain("translateY(20px)")
    expect(cards[0].style.transform).toContain("scale(0.92)")
    expect(cards[0].style.filter).toBe("brightness(0.8)")

    expect(cards[1].style.transform).toContain("translateY(10px)")
    expect(cards[1].style.transform).toContain("scale(0.96)")
    expect(cards[1].style.filter).toBe("brightness(0.9)")

    // Top card has no stack offset/filter.
    expect(cards[2].style.transform).not.toContain("translateY")
    expect(cards[2].style.filter).toBe("")
  })

  it("renders a single-card deck as just a top card with no phantom stack", () => {
    const { container } = renderSwipePage(1)
    const cards = container.querySelectorAll(".card-item-container")
    expect(cards).toHaveLength(1)
    expect(cards[0]).not.toHaveClass("stack-back")
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
    const cards = container.querySelectorAll(".card-item-container")
    const topCard = cards[cards.length - 1]

    fireEvent.pointerDown(topCard, { clientX: 0, pointerId: 1 })
    fireEvent.pointerMove(topCard, { clientX: 250, pointerId: 1 })

    const right = container.querySelector(".glow-right") as HTMLElement
    const left = container.querySelector(".glow-left") as HTMLElement
    expect(right.style.opacity).toBe("1")
    expect(left.style.opacity).toBe("0")
  })

  it("clamps left-glow opacity to 1 once dragged well past the threshold", () => {
    const { container } = renderSwipePage()
    const cards = container.querySelectorAll(".card-item-container")
    const topCard = cards[cards.length - 1]

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

    fireEvent.pointerDown(topCard, { clientX: 0, pointerId: 1 })
    fireEvent.pointerMove(topCard, { clientX: 20, pointerId: 1 })

    const right = container.querySelector(".glow-right") as HTMLElement
    expect(right.style.opacity).toBe("0")
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
})
