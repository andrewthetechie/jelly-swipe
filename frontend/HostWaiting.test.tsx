import { fireEvent, screen, waitFor } from "@testing-library/react"
import HostWaiting from "./HostWaiting"
import SwipePage from "./SwipePage"
import { renderWithRoom } from "./test/renderWithRoom"
import { mockFetch } from "./test/mockFetch"
import { SSEContextProvider } from "./SSEContextProvider"

function getRoomState() {
  return JSON.parse(screen.getByTestId("room-state").textContent ?? "{}");
}

function renderSwipePage() {
  const utils = renderWithRoom(
    <SSEContextProvider>
      <SwipePage />
    </SSEContextProvider>,
    { currentRoomCode: "1234", roomReady: false }
  )

  return {
    ...utils,
  }
}

describe("HostWaiting - Room Code rendering", () => {
    it("renders the room code as its own prominent element", () => {
        renderWithRoom(
            <HostWaiting endSession={vi.fn()}/>,
            { currentRoomCode: "1234" }
        )
        // Label and code are split so the code can be set in the display face.
        expect(screen.getByText("Room Code")).toBeInTheDocument()
        expect(screen.getByTestId("room-code")).toHaveTextContent("1234")
    })
})

describe("HostWaiting — end session (3-part network contract)", () => {
  it("POSTs to /room/{code}/quit, then clears the room code on success", async () => {
    const spy = mockFetch({ ok: true, body: { pairing_code: "1234" } })
    renderSwipePage()

    fireEvent.click(screen.getByText("End Session"))

    // 1. The request: correct URL (.href on the URL object) + method.
    await waitFor(() => expect(spy).toHaveBeenCalledTimes(1))
    const [url, options] = spy.mock.calls[0]
    expect((url as URL).href).toMatch(/\/room\/1234\/quit$/)
    expect((options as RequestInit).method).toBe("POST")

    // 2. The success effect: currentRoomCode is cleared.
    await waitFor(() => expect(getRoomState()).toMatchObject({ currentRoomCode: null }))
  })

  it("leaves the room code untouched when quit responds non-ok", async () => {
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {})
    const spy = mockFetch({ ok: false })
    renderSwipePage()

    fireEvent.click(screen.getByText("End Session"))

    await waitFor(() => expect(spy).toHaveBeenCalled())
    expect(getRoomState()).toMatchObject({ currentRoomCode: "1234" })

    errSpy.mockRestore()
  })

  it("leaves the room code untouched and does not throw when the request fails", async () => {
    // Silence the expected console.error so the failure path stays quiet.
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {})
    const spy = mockFetch({ reject: true })
  renderSwipePage()

    fireEvent.click(screen.getByText("End Session"))

    // 3. The failure path: the request was attempted, but the success effect
    // never runs and nothing throws.
    await waitFor(() => expect(spy).toHaveBeenCalled())
    expect(getRoomState()).toMatchObject({ currentRoomCode: "1234" })

    errSpy.mockRestore()
  })
})
