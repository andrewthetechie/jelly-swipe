import { fireEvent, screen, waitFor } from "@testing-library/react"
import HostWaiting from "./HostWaiting"
import SwipePage from "./SwipePage"
import { renderWithRoom } from "./test/renderWithRoom"
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

describe("HostWaiting - Room Code rendering", () => {
    it("renders the correct room code", () => {
        renderWithRoom(
            <HostWaiting endSession={vi.fn()}/>,
            { currentRoomCode: "1234" }
        )
        expect(
            screen.queryByText("Room Code: 1234")
        ).toBeInTheDocument()
    })
})

describe("HostWaiting — end session (3-part network contract)", () => {
  it("POSTs to /room/{code}/quit, then clears the room code on success", async () => {
    const spy = mockFetch({ ok: true, body: { pairing_code: "1234" } })
    const { ctx } = renderWithRoom(
      <SSEContextProvider>
        <SwipePage cardDeck={makeDeck(2)} matchFound={false} handleMatchClose={vi.fn()} matchItem={DEFAULT_MATCHITEM} />
      </SSEContextProvider>, 
      { currentRoomCode: "1234", roomReady: false}
    )

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
    const { ctx } = renderWithRoom(
      <SSEContextProvider>
        <SwipePage cardDeck={makeDeck(2)} matchFound={false} handleMatchClose={vi.fn()} matchItem={DEFAULT_MATCHITEM} />
      </SSEContextProvider>, 
      { currentRoomCode: "1234", roomReady: false }
    )

    fireEvent.click(screen.getByText("End Session"))

    await waitFor(() => expect(spy).toHaveBeenCalled())
    expect(ctx.setCurrentRoomCode).not.toHaveBeenCalled()

    errSpy.mockRestore()    
  })

  it("leaves the room code untouched and does not throw when the request fails", async () => {
    // Silence the expected console.error so the failure path stays quiet.
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {})
    const spy = mockFetch({ reject: true })
   const { ctx } = renderWithRoom(
      <SSEContextProvider>
        <SwipePage cardDeck={makeDeck(2)} matchFound={false} handleMatchClose={vi.fn()} matchItem={DEFAULT_MATCHITEM} />
      </SSEContextProvider>, 
      { currentRoomCode: "1234", roomReady: false }
    )

    fireEvent.click(screen.getByText("End Session"))

    // 3. The failure path: the request was attempted, but the success effect
    // never runs and nothing throws.
    await waitFor(() => expect(spy).toHaveBeenCalled())
    expect(ctx.setCurrentRoomCode).not.toHaveBeenCalled()

    errSpy.mockRestore()
  })
})