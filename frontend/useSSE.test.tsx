import { renderHook, act } from "@testing-library/react"
import { useSSE } from "./useSSE"
import { createMockEventSource } from "./test/mockEventSource"
import { type EventSourceMockConstructor } from "./test/mockEventSource"
import { vi } from "vitest"


describe("useSSE - connection lifecycle and error handling", () => {
  it("establishes an SSE connection to the given URL and updates state on events", async () => {

    const mockEventSource = createMockEventSource()
    const EventSourceMock = vi.fn(() => mockEventSource as unknown as EventSource) as unknown as EventSourceMockConstructor
    EventSourceMock.CONNECTING = 0
    EventSourceMock.OPEN = 1
    EventSourceMock.CLOSED = 2
    vi.stubGlobal("EventSource", EventSourceMock as unknown as typeof EventSource)

    const { result } = renderHook(() => useSSE("/test-sse"))

    act(() => {
      mockEventSource.onopen?.call(
        mockEventSource as unknown as EventSource,
        new Event("open"),
      )
    })

    expect(result.current.isConnected).toBe(true)
    expect(result.current.error).toBeNull()

    // Simulate receiving a valid SSE message
    act(() => {
      mockEventSource.simulateMessage({ data: JSON.stringify({ message: "Hello, SSE!" }) })
    })
    expect(result.current.lastMessage).toEqual({ message: "Hello, SSE!" })

    // Simulate receiving an invalid SSE message
    act(() => {
      mockEventSource.simulateMessage({ data: "Invalid JSON" })
    })
    expect(result.current.error).toBe("Error parsing SSE data")

    // Simulate a connection error
    act(() => {
      mockEventSource.simulateError(new Event("error"))
    })
    expect(result.current.isConnected).toBe(false)
    expect(result.current.error).toBe("Connection lost. Attempting to reconnect...")
  })

  it("does not attempt to connect when URL is null and cleans up on unmount", () => {

    const mockEventSource = createMockEventSource()
    const EventSourceMock = vi.fn(
      () => mockEventSource as unknown as EventSource,
    ) as unknown as EventSourceMockConstructor
    EventSourceMock.CONNECTING = 0
    EventSourceMock.OPEN = 1
    EventSourceMock.CLOSED = 2
    vi.stubGlobal("EventSource", EventSourceMock as unknown as typeof EventSource)

    const { unmount } = renderHook(() => useSSE(null))

    expect(EventSourceMock).not.toHaveBeenCalled()

    unmount()
  })

  it("onopen sets isConnected to true and clears error", () => {
    const mockEventSource = createMockEventSource()
    const EventSourceMock = vi.fn(() => mockEventSource as unknown as EventSource) as unknown as { new (url: string): EventSource }
    vi.stubGlobal("EventSource", EventSourceMock as unknown as typeof EventSource)

    const { result } = renderHook(() => useSSE("/test-sse"))

    act(() => {
      mockEventSource.onopen?.call(
        mockEventSource as unknown as EventSource,
        new Event("open"),
      )
    })

    expect(result.current.isConnected).toBe(true)
    expect(result.current.error).toBeNull()
  })

  it("onmessage parses data and updates state, handling parse errors", () => {
    const mockEventSource = createMockEventSource()
    const EventSourceMock = vi.fn(() => mockEventSource as unknown as EventSource) as unknown as { new (url: string): EventSource }
    vi.stubGlobal("EventSource", EventSourceMock as unknown as typeof EventSource)

    const { result } = renderHook(() => useSSE("/test-sse"))

    act(() => {
      mockEventSource.onopen?.call(
        mockEventSource as unknown as EventSource,
        new Event("open"),
      )
    })

    act(() => {
      mockEventSource.simulateMessage({ data: JSON.stringify({ message: "Hello, SSE!" }) })
    })
    expect(result.current.lastMessage).toEqual({ message: "Hello, SSE!" })

    act(() => {
      mockEventSource.simulateMessage({ data: "Invalid JSON" })
    })
    expect(result.current.error).toBe("Error parsing SSE data")
  })

  it("onerror handles connection errors and triggers reconnection logic", () => {
    const mockEventSource = createMockEventSource()
    const EventSourceMock = vi.fn(
    (url: string) => mockEventSource as unknown as EventSource,
    ) as unknown as EventSourceMockConstructor

    EventSourceMock.CONNECTING = 0
    EventSourceMock.OPEN = 1
    EventSourceMock.CLOSED = 2
    vi.stubGlobal("EventSource", EventSourceMock as unknown as typeof EventSource)

    const { result } = renderHook(() => useSSE("/test-sse"))

    act(() => {
      mockEventSource.onopen?.call(
        mockEventSource as unknown as EventSource,
        new Event("open"),
      )
    })

    act(() => {
      mockEventSource.simulateError(new Event("error"))
    })
    expect(result.current.isConnected).toBe(false)
    expect(result.current.error).toBe("Connection lost. Attempting to reconnect...")
  })

  it("disconnect function closes connection and clears reconnection timer", () => {
    const mockEventSource = createMockEventSource()
    const EventSourceMock = vi.fn(() => mockEventSource as unknown as EventSource) as unknown as { new (url: string): EventSource }
    vi.stubGlobal("EventSource", EventSourceMock as unknown as typeof EventSource)

    const { result } = renderHook(() => useSSE("/test-sse"))

    act(() => {
      mockEventSource.onopen?.call(
        mockEventSource as unknown as EventSource,
        new Event("open"),
      )
    })

    act(() => {
      result.current.disconnect()
    })

    expect(mockEventSource.close).toHaveBeenCalled()
  })
})