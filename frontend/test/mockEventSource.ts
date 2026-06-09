import { vi } from "vitest"

export type MockEventSource = {
  url: string
  withCredentials: boolean
  readyState: number
  onopen: ((this: EventSource, ev: Event) => any) | null
  onmessage: ((this: EventSource, ev: MessageEvent) => any) | null
  onerror: ((this: EventSource, ev: Event) => any) | null
  close: ReturnType<typeof vi.fn>
  addEventListener: (...args: unknown[]) => void
  removeEventListener: (...args: unknown[]) => void
  dispatchEvent: (event: Event) => boolean
  simulateMessage: (event: { data: string }) => void
  simulateError: (event: Event) => void
}

export type EventSourceMockConstructor = {
    new (url: string): EventSource
    CONNECTING: number
    OPEN: number
    CLOSED: number
}

export function createMockEventSource(): MockEventSource {
  const mock: MockEventSource = {
    url: "",
    withCredentials: false,
    readyState: 1,
    onopen: null,
    onmessage: null,
    onerror: null,
    close: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(() => true),
    simulateMessage(this: MockEventSource, event: { data: string }) {
      if (this.onmessage) {
        this.onmessage.call(
          this as unknown as EventSource,
          new MessageEvent("message", { data: event.data }),
        )
      }
    },
    simulateError(this: MockEventSource, event: Event) {
      this.readyState = 2
      if (this.onerror) {
        this.onerror.call(this as unknown as EventSource, event)
      }
    },
  }

  return mock
}