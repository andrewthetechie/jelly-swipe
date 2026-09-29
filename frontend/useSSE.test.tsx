import { renderHook, act } from "@testing-library/react"
import { useSSE } from "./useSSE"
import { createMockEventSource } from "./test/mockEventSource"
import { type EventSourceMockConstructor } from "./test/mockEventSource"
import { vi } from "vitest"


describe("useSSE - connection lifecycle and error handling", () => {
  it("establishes an SSE connection to the given URL and updates state on events", async () => {

    const mockEventSource = createMockEventSource()
    const EventSourceMock = vi.fn(function () { return mockEventSource as unknown as EventSource }) as unknown as EventSourceMockConstructor 
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
      function () { mockEventSource as unknown as EventSource },
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
    const EventSourceMock = vi.fn(function () { return mockEventSource as unknown as EventSource }) as unknown as { new (url: string): EventSource }
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
    const EventSourceMock = vi.fn(function () { return mockEventSource as unknown as EventSource }) as unknown as { new (url: string): EventSource }
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
      function () { return mockEventSource as unknown as EventSource },
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
    const EventSourceMock = vi.fn(function () { return mockEventSource as unknown as EventSource }) as unknown as { new (url: string): EventSource }
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

describe("useSSE - cursor forwarding and reconnect behavior", () => {
  beforeEach(() => {
    vi.spyOn(console, "log").mockImplementation(() => {})
    vi.spyOn(console, "error").mockImplementation(() => {})
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  const setup = () => {
    const mockEventSource = createMockEventSource()
    const EventSourceMock = vi.fn(function () { return mockEventSource as unknown as EventSource })
    Object.assign(EventSourceMock, { CONNECTING: 0, OPEN: 1, CLOSED: 2 })
    vi.stubGlobal("EventSource", EventSourceMock as unknown as typeof EventSource)
    return { mockEventSource, EventSourceMock }
  }

  const streamUrlOf = (EventSourceMock: ReturnType<typeof vi.fn>, callIndex: number) => {
    const arg = EventSourceMock.mock.calls[callIndex][0]
    return new URL(String(arg))
  }

  it("fresh bootstrap sends no after_event_id", () => {
    const { EventSourceMock } = setup()

    renderHook(() => useSSE("/test-sse"))

    expect(EventSourceMock).toHaveBeenCalledTimes(1)
    expect(streamUrlOf(EventSourceMock, 0).searchParams.get("after_event_id")).toBeNull()
  })

  it("forwards a lastEventId cursor and reconnects with after_event_id after 3000 ms", () => {
    vi.useFakeTimers()
    const { mockEventSource, EventSourceMock } = setup()

    const { result } = renderHook(() => useSSE("/test-sse"))

    act(() => {
      mockEventSource.onopen?.call(
        mockEventSource as unknown as EventSource,
        new Event("open"),
      )
    })

    act(() => {
      mockEventSource.simulateMessage({ data: JSON.stringify({ message: "hello" }), lastEventId: "42" })
    })

    act(() => {
      mockEventSource.simulateError(new Event("error"))
    })
    expect(result.current.isConnected).toBe(false)
    expect(result.current.error).toBe("Connection lost. Attempting to reconnect...")

    // No reconnect before 3000 ms elapses.
    act(() => {
      vi.advanceTimersByTime(2999)
    })
    expect(EventSourceMock).toHaveBeenCalledTimes(1)

    act(() => {
      vi.advanceTimersByTime(1)
    })
    expect(EventSourceMock).toHaveBeenCalledTimes(2)
    expect(streamUrlOf(EventSourceMock, 1).searchParams.get("after_event_id")).toBe("42")
  })

  it("session_reset is not exposed via lastMessage, closes the stream, and reconnects after 1000 ms without after_event_id", () => {
    vi.useFakeTimers()
    const { mockEventSource, EventSourceMock } = setup()

    const { result } = renderHook(() => useSSE("/test-sse"))

    act(() => {
      mockEventSource.onopen?.call(
        mockEventSource as unknown as EventSource,
        new Event("open"),
      )
    })

    act(() => {
      mockEventSource.simulateMessage({ data: JSON.stringify({ message: "hello" }), lastEventId: "42" })
    })

    act(() => {
      mockEventSource.simulateMessage({ data: JSON.stringify({ event_type: "session_reset" }) })
    })
    // The session_reset payload itself is not exposed via lastMessage.
    expect(result.current.lastMessage).toEqual({ message: "hello" })
    expect(mockEventSource.close).toHaveBeenCalled()

    act(() => {
      vi.advanceTimersByTime(1000)
    })
    expect(EventSourceMock).toHaveBeenCalledTimes(2)
    expect(streamUrlOf(EventSourceMock, 1).searchParams.get("after_event_id")).toBeNull()
  })

  it("clears lastMessage, error, and isConnected when the URL changes (room switch)", () => {
    const { mockEventSource, EventSourceMock } = setup()

    const { result, rerender } = renderHook(({ url }: { url: string | null }) => useSSE(url), {
      initialProps: { url: "/test-sse" },
    })

    act(() => {
      mockEventSource.onopen?.call(
        mockEventSource as unknown as EventSource,
        new Event("open"),
      )
    })
    act(() => {
      mockEventSource.simulateMessage({ data: JSON.stringify({ message: "hello" }), lastEventId: "42" })
    })
    expect(result.current.lastMessage).toEqual({ message: "hello" })
    expect(result.current.isConnected).toBe(true)

    // Simulate a room switch: url change triggers the shared teardown before reopening.
    rerender({ url: "/test-sse-2" })

    expect(result.current.lastMessage).toBeNull()
    expect(result.current.error).toBeNull()
    expect(result.current.isConnected).toBe(false)
    expect(EventSourceMock).toHaveBeenCalledTimes(2)
  })

  it("does not move the cursor backwards", () => {
    vi.useFakeTimers()
    const { mockEventSource, EventSourceMock } = setup()

    renderHook(() => useSSE("/test-sse"))

    act(() => {
      mockEventSource.onopen?.call(
        mockEventSource as unknown as EventSource,
        new Event("open"),
      )
    })

    act(() => {
      mockEventSource.simulateMessage({ data: JSON.stringify({ message: "hello" }), lastEventId: "50" })
    })
    act(() => {
      mockEventSource.simulateMessage({ data: JSON.stringify({ message: "hello" }), lastEventId: "10" })
    })

    act(() => {
      mockEventSource.simulateError(new Event("error"))
    })
    act(() => {
      vi.advanceTimersByTime(3000)
    })
    expect(EventSourceMock).toHaveBeenCalledTimes(2)
    expect(streamUrlOf(EventSourceMock, 1).searchParams.get("after_event_id")).toBe("50")
  })

  it("catches an EventSource constructor throw on mount and reconnect, setting the SSE error instead of propagating", () => {
    const { mockEventSource, EventSourceMock } = setup()
    let calls = 0
    EventSourceMock.mockImplementation(function () {
      calls += 1
      if (calls <= 2) {
        throw new Error("constructor failed")
      }
      return mockEventSource as unknown as EventSource
    })

    const { result } = renderHook(() => useSSE("/test-sse"))

    expect(result.current.error).toBe("Error establishing SSE connection")
    expect(EventSourceMock).toHaveBeenCalledTimes(1)

    // A reconnect flows through the same guarded path and is swallowed too.
    act(() => {
      result.current.connect()
    })
    expect(result.current.error).toBe("Error establishing SSE connection")
    expect(EventSourceMock).toHaveBeenCalledTimes(2)
  })

  it("teardown cancels a scheduled reconnect when the URL changes, so only one stream opens for the new URL", () => {
    vi.useFakeTimers()
    const { mockEventSource, EventSourceMock } = setup()

    const { rerender } = renderHook(({ url }: { url: string | null }) => useSSE(url), {
      initialProps: { url: "/test-sse" },
    })

    act(() => {
      mockEventSource.onopen?.call(
        mockEventSource as unknown as EventSource,
        new Event("open"),
      )
    })

    act(() => {
      mockEventSource.simulateError(new Event("error"))
    })

    // Reconnect is scheduled 3000 ms out; not yet fired.
    act(() => {
      vi.advanceTimersByTime(2999)
    })
    expect(EventSourceMock).toHaveBeenCalledTimes(1)

    // A URL change runs teardown(), which clears the pending reconnect timer, then
    // reopens for the new URL.
    rerender({ url: "/test-sse-2" })
    expect(EventSourceMock).toHaveBeenCalledTimes(2)
    expect(streamUrlOf(EventSourceMock, 1).searchParams.get("after_event_id")).toBeNull()

    // Advance past the original 3000 ms window: the stale timer must not fire a
    // second stream for the new URL.
    act(() => {
      vi.advanceTimersByTime(1)
    })
    expect(EventSourceMock).toHaveBeenCalledTimes(2)
  })
})