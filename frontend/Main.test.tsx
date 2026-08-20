import { screen } from "@testing-library/react"
import Main from "./Main"
import { renderWithRoom } from "./test/renderWithRoom"
import { SSEContextProvider } from "./SSEContextProvider"
import { mockFetch } from "./test/mockFetch"

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
