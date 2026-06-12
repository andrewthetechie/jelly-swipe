import { render } from "@testing-library/react"
import { SSEContextProvider, useSSEContext } from "./SSEContextProvider"
import { renderWithRoom } from "./test/renderWithRoom"
import { useSSE } from "./useSSE"
import { apiUrl } from "./api"

vi.mock("./useSSE")
vi.mock("./api")

const mockUseSSE = vi.mocked(useSSE)
const mockApiUrl = vi.mocked(apiUrl)

function TestConsumer() {
    const { sseData, sseError, isConnected } = useSSEContext()

    return (
        <>
            <div data-testid="data">{JSON.stringify(sseData)}</div>
            <div data-testid="error">{String(sseError)}</div>
            <div data-testid="connected">{String(isConnected)}</div>
        </>
    )
}

function OutsideProviderConsumer() {
    useSSEContext()
    return null
}

describe("SSEContextProvider - provider behavior", () => {
    afterEach(() => {
        vi.clearAllMocks()
    })

    it("returns correct steamUrl with a currentRoomCode", () => {
        mockApiUrl.mockReturnValue(
            new URL("http://localhost:5005/room/1234/stream")
        )

        mockUseSSE.mockReturnValue({
            data: null,
            error: null,
            isConnected: true,
            connect: vi.fn(),
            disconnect: vi.fn(),
        })

        renderWithRoom(
            <SSEContextProvider>
                <div>child</div>
            </SSEContextProvider>,
            { currentRoomCode: "1234" }
        )

        expect(mockApiUrl).toHaveBeenCalledTimes(1)
        expect(mockApiUrl).toHaveBeenCalledWith("/room/1234/stream")
        expect(mockUseSSE).toHaveBeenCalledWith("http://localhost:5005/room/1234/stream")
    })

    it("passes null to useSSE when currentRoomCode is null", () => {
        mockUseSSE.mockReturnValue({
            data: {},
            error: null,
            isConnected: false,
            connect: vi.fn(),
            disconnect: vi.fn(),
        })

        renderWithRoom(
            <SSEContextProvider>
                <div>child</div>
            </SSEContextProvider>,
            { currentRoomCode: null }
        )

        expect(mockApiUrl).not.toHaveBeenCalled()
        expect(mockUseSSE).toHaveBeenCalledTimes(1)
        expect(mockUseSSE).toHaveBeenCalledWith(null)
    })

    it("provides values returned by useSSE", () => {
        mockApiUrl.mockReturnValue(
            new URL("http://localhost:5005/room/1234/stream")
        )

        mockUseSSE.mockReturnValue({
            data: { roomCode: "1234" },
            error: "boom",
            isConnected: true,
            connect: vi.fn(),
            disconnect: vi.fn(),
        })

        const { getByTestId } = renderWithRoom(
            <SSEContextProvider>
                <TestConsumer />
            </SSEContextProvider>,
            { currentRoomCode: "1234" }
        )

        expect(getByTestId("data").textContent).toBe(
            JSON.stringify({ roomCode: "1234" })
        )

        expect(getByTestId("error").textContent).toBe("boom")

        expect(getByTestId("connected").textContent).toBe("true")

    })

    it("useSSEContext throws when used outside the provider", () => {
        expect(() => 
            render(<OutsideProviderConsumer />)
        ).toThrow(
            "useSSEContext must be used within SSEContextProvider"
        )
    })
})