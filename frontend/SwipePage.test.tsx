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
  it("renders at most 5 cards (visibleCards = deck.slice(0,5)) in reverse order", () => {
    const { container } = renderSwipePage(7)
    const cards = container.querySelectorAll(".card-item-container")
    expect(cards).toHaveLength(5)

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
