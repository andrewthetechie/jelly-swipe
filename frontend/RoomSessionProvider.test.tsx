// RoomSessionProvider.test.tsx — render-level coverage for the real provider's
// SSE forwarding effect (RoomSessionProvider.tsx:71-77).
//
// The room-session store extraction (issue #398) left RoomSessionProvider as a
// thin shell that forwards `sseData`/`sseError` from `useSSEContext` to the
// store's `applySseEvent`/`reportSseError`. After the renderHook harness was
// deleted and every component suite rendered via `renderWithRoom` with a
// neutral `{ sseData: null }` SSE context, no test drove events through the
// real shell — so a regression there (dropped call, wrong deps, wrong branch)
// would pass the whole suite while silently disabling match popups, partner-
// ready bootstrap, remote genre/hide_watched refetch, and session_closed auto-
// exit in production.
//
// This suite mounts the real RoomSessionProvider inside RoomContextProvider plus
// an injected `SSEContext.Provider` value, with a fake RoomSessionApi injected
// via the provider's `api` prop. No renderHook, no module-wide vi.mock — direct
// render plus `waitFor` assertions keep it deterministic.
import { render, screen, waitFor } from "@testing-library/react"
import React from "react"
import { RoomContextProvider, useRoomSetterContext, useRoomStateContext } from "./RoomContextProvider"
import { SSEContext, type SSEContextType } from "./SSEContextProvider"
import { RoomSessionProvider, useRoomSession } from "./RoomSessionProvider"
import type { RoomSessionApi } from "./roomSessionStore"
import type { SSEEvent } from "./types"
import { makeDeck } from "./test/fixtures"

const ROOM_CODE = "1234"

/** A fake RoomSessionApi that never touches the network. */
function makeApi(): RoomSessionApi {
    return {
        fetchDeck: vi.fn().mockResolvedValue(makeDeck(2)),
        postSwipe: vi.fn().mockResolvedValue(undefined),
        undoSwipe: vi.fn().mockResolvedValue(undefined),
        setGenreChoice: vi.fn().mockResolvedValue({
            deck: makeDeck(2),
            mutationEventId: 0,
            mutationType: "genre_changed",
        }),
        setWatchedFilter: vi.fn().mockResolvedValue({
            deck: makeDeck(2),
            mutationEventId: 0,
            mutationType: "hide_watched_changed",
        }),
        quitRoom: vi.fn().mockResolvedValue({ status: "ok" }),
    }
}

/** Renders the session state as JSON so tests can assert on it. */
function SessionStateProbe() {
    const { state } = useRoomSession()
    return <pre data-testid="session-state">{JSON.stringify(state)}</pre>
}

/** Renders the current room code so tests can observe the exit transition. */
function RoomCodeProbe() {
    const { currentRoomCode } = useRoomStateContext()
    return <div data-testid="room-code">{currentRoomCode ?? "null"}</div>
}

/** Seeds a room code into RoomContextProvider exactly once. */
function RoomCodeSeeder({ code }: { code: string }) {
    const { setCurrentRoomCode } = useRoomSetterContext()
    const seeded = React.useRef(false)
    React.useLayoutEffect(() => {
        if (seeded.current) return
        seeded.current = true
        setCurrentRoomCode(code)
    }, [code, setCurrentRoomCode])
    return null
}

function getSessionState(): Record<string, unknown> {
    return JSON.parse(screen.getByTestId("session-state").textContent ?? "{}")
}

/**
 * Build the provider tree for a given SSE data value. Re-rendering with a new
 * value drives the shell's SSE effect deterministically: the component types
 * stay at the same positions, so the store is preserved across rerenders and
 * only the context value changes.
 */
function buildTree(api: RoomSessionApi, sseData: SSEEvent | null): React.ReactElement {
    const sseValue: SSEContextType = { sseData, sseError: null, isConnected: true }
    return (
        <RoomContextProvider>
            <RoomCodeSeeder code={ROOM_CODE} />
            <SSEContext.Provider value={sseValue}>
                <RoomSessionProvider api={api}>
                    <SessionStateProbe />
                    <RoomCodeProbe />
                </RoomSessionProvider>
            </SSEContext.Provider>
        </RoomContextProvider>
    )
}

describe("RoomSessionProvider — SSE forwarding effect", () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it("forwards a session_bootstrap event so the store flips roomReady", async () => {
        const api = makeApi()
        const view = render(buildTree(api, null))
        // Wait for the seeded room join to settle so the store has a room code.
        await waitFor(() => expect(api.fetchDeck).toHaveBeenCalledTimes(1))

        const bootstrap: SSEEvent = {
            event_type: "session_bootstrap",
            instance_id: "inst-1",
            ready: true,
            genre: "All",
            solo: false,
            hide_watched: false,
            replay_boundary: 0,
        }
        view.rerender(buildTree(api, bootstrap))

        await waitFor(() => expect(getSessionState().roomReady).toBe(true))
    })

    it("forwards a session_ready event so the store flips roomReady", async () => {
        const api = makeApi()
        const view = render(buildTree(api, null))
        await waitFor(() => expect(api.fetchDeck).toHaveBeenCalledTimes(1))

        view.rerender(buildTree(api, { event_type: "session_ready", event_id: 7 }))

        await waitFor(() => expect(getSessionState().roomReady).toBe(true))
    })

    it("forwards a remote genre_changed event and triggers a deck refetch", async () => {
        const api = makeApi()
        const view = render(buildTree(api, null))
        await waitFor(() => expect(api.fetchDeck).toHaveBeenCalledTimes(1))

        view.rerender(buildTree(api, { event_type: "genre_changed", event_id: 9, genre: "Action" }))

        // The remote genre change is not a local echo, so the store refetches.
        await waitFor(() => expect(api.fetchDeck).toHaveBeenCalledTimes(2))
        await waitFor(() => expect(getSessionState().genre).toBe("Action"))
    })

    it("forwards a session_closed event and exits the room via setCurrentRoomCode(null)", async () => {
        const api = makeApi()
        const view = render(buildTree(api, null))
        await waitFor(() => expect(api.fetchDeck).toHaveBeenCalledTimes(1))
        expect(screen.getByTestId("room-code").textContent).toBe(ROOM_CODE)

        view.rerender(buildTree(api, { event_type: "session_closed", event_id: 11 }))

        await waitFor(() => expect(screen.getByTestId("room-code").textContent).toBe("null"))
        await waitFor(() => expect(getSessionState().roomReady).toBe(false))
    })
})
