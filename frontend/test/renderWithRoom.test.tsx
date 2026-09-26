import { screen, waitFor } from "@testing-library/react"
import { renderWithRoom } from "./renderWithRoom"
import { useRoomSession } from "../RoomSessionProvider"
import { makeDeck } from "./fixtures"

// The fake api delegates to the roomApi module when a function is a vi.mock.
// A bare vi.fn() for fetchDeck (no resolved value) falls through to the seeded
// deck, which is how the surviving-seed contract is exercised below.
vi.mock("./../roomApi", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../roomApi")>()),
  fetchDeck: vi.fn(),
  quitRoom: vi.fn(),
}))

function SessionStateProbe() {
  const { state } = useRoomSession()
  return <pre data-testid="session-state" hidden>{JSON.stringify(state)}</pre>
}

function getSessionState() {
  return JSON.parse(screen.getByTestId("session-state").textContent ?? "{}")
}

// Pins the surviving-seed semantics the README documents for renderWithRoom:
// cardDeck survives only when a currentRoomCode is passed (the seeded deck is
// served by the join fetch); without a room code the real provider resets it.
// swipeHistory is not a valid seed and is omitted from the overrides type.
describe("renderWithRoom session-seeding contract", () => {
  it("serves the seeded cardDeck through the join fetch when a room code is set", async () => {
    renderWithRoom(<SessionStateProbe />, {
      currentRoomCode: "1234",
      cardDeck: makeDeck(2),
    })

    await waitFor(() => expect(getSessionState().cardDeck).toHaveLength(2))
    expect(getSessionState().cardDeck[0]).toMatchObject({ title: "Movie 1" })
  })

  it("resets the seeded deck when no room code is passed", async () => {
    renderWithRoom(<SessionStateProbe />, {
      cardDeck: makeDeck(2),
    })

    await waitFor(() => expect(getSessionState().cardDeck).toEqual([]))
    expect(getSessionState().swipeHistory).toEqual([])
  })
})
