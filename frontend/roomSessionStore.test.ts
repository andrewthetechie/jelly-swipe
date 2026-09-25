import { describe, expect, it, vi } from "vitest"
import { RoomSessionStore, type RoomSessionApi } from "./roomSessionStore"
import { makeCard } from "./test/fixtures"
import type { MutationChangeResult } from "./types"

const ROOM_CODE = "1234"

function makeApi(overrides: Partial<RoomSessionApi> = {}): RoomSessionApi {
    return {
        fetchDeck: vi.fn(),
        postSwipe: vi.fn(),
        undoSwipe: vi.fn(),
        setGenreChoice: vi.fn(),
        setWatchedFilter: vi.fn(),
        quitRoom: vi.fn(),
        ...overrides,
    }
}

function makeStore(api: RoomSessionApi, onExitRoom: () => void = () => {}) {
    return new RoomSessionStore({ api, onExitRoom })
}

/** Join a room and wait for the join fetch (panel target) to resolve. */
async function joinRoom(store: RoomSessionStore, api: RoomSessionApi): Promise<void> {
    store.onRoomCodeChanged(ROOM_CODE)
    await vi.waitFor(() => expect(api.fetchDeck).toHaveBeenCalledTimes(1))
    await vi.waitFor(() => expect(store.getState().deckLoaded).toBe(true))
}

describe("RoomSessionStore commands", () => {
    it("swipe success pops the deck and appends history", async () => {
        const first = makeCard({ mediaId: "m-1", title: "Movie m-1" })
        const second = makeCard({ mediaId: "m-2", title: "Movie m-2" })
        const api = makeApi({
            fetchDeck: vi.fn().mockResolvedValue([first, second]),
            postSwipe: vi.fn().mockResolvedValue(undefined),
        })
        const store = makeStore(api)
        await joinRoom(store, api)

        await store.swipe(first, "right")

        expect(api.postSwipe).toHaveBeenCalledWith(ROOM_CODE, "m-1", "right")
        expect(store.getState().swipeHistory).toEqual([first])
        expect(store.getState().cardDeck).toEqual([second])
    })

    it("swipe failure sets lastError, leaves the deck untouched, and re-throws", async () => {
        const first = makeCard({ mediaId: "m-1", title: "Movie m-1" })
        const second = makeCard({ mediaId: "m-2", title: "Movie m-2" })
        const api = makeApi({
            fetchDeck: vi.fn().mockResolvedValue([first, second]),
            postSwipe: vi.fn().mockRejectedValue(new Error("swipe failed")),
        })
        const store = makeStore(api)
        await joinRoom(store, api)
        const errorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined)

        await expect(store.swipe(first, "left")).rejects.toThrow("swipe failed")

        expect(store.getState().cardDeck).toEqual([first, second])
        expect(store.getState().swipeHistory).toEqual([])
        expect(store.getState().lastError).toContain("Couldn't save that swipe")
        errorSpy.mockRestore()
    })

    it("swipe throws without a room code", async () => {
        const api = makeApi()
        const store = makeStore(api)

        await expect(store.swipe(makeCard(), "right")).rejects.toThrow("Cannot send swipe without currentRoomCode")
    })

    it("undo with empty history no-ops without calling the API", async () => {
        const first = makeCard({ mediaId: "m-1", title: "Movie m-1" })
        const api = makeApi({ fetchDeck: vi.fn().mockResolvedValue([first]) })
        const store = makeStore(api)
        await joinRoom(store, api)
        const errorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined)

        await store.undo()

        expect(api.undoSwipe).not.toHaveBeenCalled()
        expect(errorSpy).toHaveBeenCalledWith("Cannot undo without swipe history")
        expect(store.getState().cardDeck).toEqual([first])
        errorSpy.mockRestore()
    })

    it("undo success restores the card to the deck front", async () => {
        const first = makeCard({ mediaId: "m-1", title: "Movie m-1" })
        const second = makeCard({ mediaId: "m-2", title: "Movie m-2" })
        const api = makeApi({
            fetchDeck: vi.fn().mockResolvedValue([first, second]),
            postSwipe: vi.fn().mockResolvedValue(undefined),
            undoSwipe: vi.fn().mockResolvedValue(undefined),
        })
        const store = makeStore(api)
        await joinRoom(store, api)

        await store.swipe(first, "right")
        await store.undo()

        expect(api.undoSwipe).toHaveBeenCalledWith(ROOM_CODE, "m-1")
        expect(store.getState().cardDeck).toEqual([first, second])
        expect(store.getState().swipeHistory).toEqual([])
    })

    it("confirmGenre success replaces the deck, clears history, and sets the genre", async () => {
        const refreshedDeck = [makeCard({ mediaId: "m-3", title: "Movie m-3" })]
        const api = makeApi({
            fetchDeck: vi.fn().mockResolvedValue([makeCard({ mediaId: "m-1", title: "Movie m-1" })]),
            setGenreChoice: vi.fn().mockResolvedValue({
                deck: refreshedDeck,
                mutationEventId: 5,
                mutationType: "genre_changed",
            }),
        })
        const store = makeStore(api)
        await joinRoom(store, api)

        const ok = await store.confirmGenre("Comedy")

        expect(ok).toBe(true)
        expect(api.setGenreChoice).toHaveBeenCalledWith(ROOM_CODE, "Comedy")
        expect(store.getState().genre).toBe("Comedy")
        expect(store.getState().cardDeck).toEqual(refreshedDeck)
        expect(store.getState().swipeHistory).toEqual([])
    })

    it("confirmGenre failure returns false and leaves genre/deck untouched", async () => {
        const first = makeCard({ mediaId: "m-1", title: "Movie m-1" })
        const second = makeCard({ mediaId: "m-2", title: "Movie m-2" })
        const api = makeApi({
            fetchDeck: vi.fn().mockResolvedValue([first, second]),
            setGenreChoice: vi.fn().mockRejectedValue(new Error("genre failed")),
        })
        const store = makeStore(api)
        await joinRoom(store, api)
        const errorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined)

        const ok = await store.confirmGenre("Comedy")

        expect(ok).toBe(false)
        expect(store.getState().genre).toBe("All")
        expect(store.getState().cardDeck).toEqual([first, second])
        expect(store.getState().lastError).toContain("Couldn't change the genre")
        errorSpy.mockRestore()
    })

    it("toggleHideWatched reads the current hideWatched value (no stale closure)", async () => {
        const deck = [makeCard({ mediaId: "m-1", title: "Movie m-1" })]
        const api = makeApi({
            fetchDeck: vi.fn().mockResolvedValue(deck),
            setWatchedFilter: vi.fn().mockResolvedValue({
                deck,
                mutationEventId: 6,
                mutationType: "hide_watched_changed",
            }),
        })
        const store = makeStore(api)
        await joinRoom(store, api)

        await store.toggleHideWatched()
        await store.toggleHideWatched()

        expect(api.setWatchedFilter).toHaveBeenNthCalledWith(1, ROOM_CODE, true)
        expect(api.setWatchedFilter).toHaveBeenNthCalledWith(2, ROOM_CODE, false)
        expect(store.getState().hideWatched).toBe(false)
    })

    it("endSession dispatches SESSION_ENDED and calls onExitRoom", async () => {
        const api = makeApi({
            fetchDeck: vi.fn().mockResolvedValue([makeCard({ mediaId: "m-1", title: "Movie m-1" })]),
            quitRoom: vi.fn().mockResolvedValue({ status: "ok" }),
        })
        const onExitRoom = vi.fn()
        const store = makeStore(api, onExitRoom)
        await joinRoom(store, api)

        await store.endSession()

        expect(api.quitRoom).toHaveBeenCalledWith(ROOM_CODE)
        expect(onExitRoom).toHaveBeenCalled()
        expect(store.getState().roomReady).toBe(false)
        expect(store.getState().cardDeck).toEqual([])
        expect(store.getState().swipeHistory).toEqual([])
    })

    it("endSession failure sets lastError without calling onExitRoom", async () => {
        const api = makeApi({
            fetchDeck: vi.fn().mockResolvedValue([makeCard({ mediaId: "m-1", title: "Movie m-1" })]),
            quitRoom: vi.fn().mockRejectedValue(new Error("quit failed")),
        })
        const onExitRoom = vi.fn()
        const store = makeStore(api, onExitRoom)
        await joinRoom(store, api)
        const errorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined)

        await store.endSession()

        expect(onExitRoom).not.toHaveBeenCalled()
        expect(store.getState().lastError).toContain("Couldn't end the session")
        errorSpy.mockRestore()
    })

    it("dismissMatch clears matchFound", () => {
        const api = makeApi()
        const store = makeStore(api)
        store.applySseEvent({
            event_type: "match_found",
            event_id: 1,
            title: "Movie",
            media_id: "m-1",
            media_type: "movie",
        })
        expect(store.getState().matchFound).toBe(true)

        store.dismissMatch()

        expect(store.getState().matchFound).toBe(false)
    })

    it("clearError clears lastError", async () => {
        const api = makeApi({
            fetchDeck: vi.fn().mockResolvedValue([makeCard({ mediaId: "m-1", title: "Movie m-1" })]),
            postSwipe: vi.fn().mockRejectedValue(new Error("boom")),
        })
        const store = makeStore(api)
        await joinRoom(store, api)
        await store.swipe(makeCard(), "left").catch(() => {})
        expect(store.getState().lastError).not.toBeNull()

        store.clearError()

        expect(store.getState().lastError).toBeNull()
    })

    it("retryDeckFetch recovers from a join fetch failure", async () => {
        const deck = [makeCard({ mediaId: "m-1", title: "Movie m-1" })]
        const api = makeApi({
            fetchDeck: vi.fn()
                .mockRejectedValueOnce(new Error("fetch failed"))
                .mockResolvedValue(deck),
        })
        const store = makeStore(api)
        const errorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined)

        store.onRoomCodeChanged(ROOM_CODE)
        await vi.waitFor(() => expect(store.getState().deckError).toContain("Couldn't load your cards"))

        await store.retryDeckFetch()

        expect(store.getState().deckError).toBeNull()
        expect(store.getState().cardDeck).toEqual(deck)
        errorSpy.mockRestore()
    })
})

describe("RoomSessionStore deck-fetch policy", () => {
    it("join fetch failure surfaces DECK_FETCH_FAILED (panel target)", async () => {
        const api = makeApi({ fetchDeck: vi.fn().mockRejectedValue(new Error("fetch failed")) })
        const store = makeStore(api)
        const errorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined)

        store.onRoomCodeChanged(ROOM_CODE)
        await vi.waitFor(() => expect(store.getState().deckError).toContain("Couldn't load your cards"))

        expect(store.getState().lastError).toBeNull()
        errorSpy.mockRestore()
    })

    it("remote refetch failure surfaces a COMMAND_FAILED banner without blanking the loaded deck", async () => {
        const deck = [makeCard({ mediaId: "m-1", title: "Movie m-1" })]
        const api = makeApi({ fetchDeck: vi.fn().mockResolvedValue(deck) })
        const store = makeStore(api)
        await joinRoom(store, api)
        const fetchDeckMock = vi.mocked(api.fetchDeck)
        fetchDeckMock.mockClear()
        fetchDeckMock.mockRejectedValue(new Error("network down"))
        const errorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined)

        store.applySseEvent({ event_type: "genre_changed", event_id: 99, genre: "Comedy" })

        await vi.waitFor(() => expect(fetchDeckMock).toHaveBeenCalledWith(ROOM_CODE))
        await vi.waitFor(() => expect(store.getState().lastError).toContain("Couldn't refresh your cards"))
        expect(store.getState().deckError).toBeNull()
        expect(store.getState().cardDeck).toEqual(deck)
        errorSpy.mockRestore()
    })
})

describe("RoomSessionStore SSE suppression", () => {
    it("suppresses own genre echo by registered event id and updates mirrored genre", async () => {
        const api = makeApi({
            fetchDeck: vi.fn().mockResolvedValue([makeCard({ mediaId: "m-1", title: "Movie m-1" })]),
            setGenreChoice: vi.fn().mockResolvedValue({
                deck: [makeCard({ mediaId: "m-2", title: "Movie m-2" })],
                mutationEventId: 41,
                mutationType: "genre_changed",
            }),
        })
        const store = makeStore(api)
        await joinRoom(store, api)
        const fetchDeckMock = vi.mocked(api.fetchDeck)
        fetchDeckMock.mockClear()

        await store.confirmGenre("Comedy")
        store.applySseEvent({ event_type: "genre_changed", event_id: 41, genre: "Comedy" })

        expect(fetchDeckMock).not.toHaveBeenCalled()
        expect(store.getState().genre).toBe("Comedy")
    })

    it("refetches the deck on a remote genre echo (unrelated event id, nothing in flight)", async () => {
        const api = makeApi({ fetchDeck: vi.fn().mockResolvedValue([makeCard({ mediaId: "m-1", title: "Movie m-1" })]) })
        const store = makeStore(api)
        await joinRoom(store, api)
        const fetchDeckMock = vi.mocked(api.fetchDeck)
        fetchDeckMock.mockClear()

        store.applySseEvent({ event_type: "genre_changed", event_id: 99, genre: "Comedy" })

        await vi.waitFor(() => expect(fetchDeckMock).toHaveBeenCalledWith(ROOM_CODE))
        expect(store.getState().genre).toBe("Comedy")
    })

    it("suppresses own echo arriving before the POST resolves, then still honors a later remote change", async () => {
        const deckA = [makeCard({ mediaId: "m-1", title: "Movie m-1" })]
        const api = makeApi({ fetchDeck: vi.fn().mockResolvedValue(deckA) })
        let release: (r: MutationChangeResult) => void = () => {}
        api.setGenreChoice = vi.fn(() =>
            new Promise<MutationChangeResult>((res) => { release = res })
        )
        const store = makeStore(api)
        await joinRoom(store, api)
        const fetchDeckMock = vi.mocked(api.fetchDeck)
        fetchDeckMock.mockClear()

        const confirmPromise = store.confirmGenre("Comedy")

        // Own echo arrives while the POST is still in flight -> suppressed, no refetch.
        store.applySseEvent({ event_type: "genre_changed", event_id: 50, genre: "Comedy" })
        expect(fetchDeckMock).not.toHaveBeenCalled()

        // POST resolves.
        release({ deck: [makeCard({ mediaId: "m-2", title: "Movie m-2" })], mutationEventId: 60, mutationType: "genre_changed" })
        await confirmPromise

        fetchDeckMock.mockClear()

        // A later remote change must refetch (no stuck suppression).
        store.applySseEvent({ event_type: "genre_changed", event_id: 200, genre: "Drama" })
        await vi.waitFor(() => expect(fetchDeckMock).toHaveBeenCalledWith(ROOM_CODE))
    })

    it("does not leave stale suppression after a failed mutation", async () => {
        const deckA = [makeCard({ mediaId: "m-1", title: "Movie m-1" })]
        const api = makeApi({
            fetchDeck: vi.fn().mockResolvedValue(deckA),
            setWatchedFilter: vi.fn().mockRejectedValue(new Error("boom")),
        })
        const store = makeStore(api)
        await joinRoom(store, api)
        const fetchDeckMock = vi.mocked(api.fetchDeck)
        fetchDeckMock.mockClear()
        const errorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined)

        await store.toggleHideWatched()
        expect(store.getState().lastError).toContain("Couldn't update the watched filter")

        // A remote hide_watched change must still refetch.
        store.applySseEvent({ event_type: "hide_watched_changed", event_id: 77, hide_watched: true })
        await vi.waitFor(() => expect(fetchDeckMock).toHaveBeenCalledWith(ROOM_CODE))
        errorSpy.mockRestore()
    })

    it("keeps ignoredEventIds across session_reset while clearing in-flight", async () => {
        const api = makeApi({
            fetchDeck: vi.fn().mockResolvedValue([makeCard({ mediaId: "m-1", title: "Movie m-1" })]),
            setGenreChoice: vi.fn().mockResolvedValue({
                deck: [makeCard({ mediaId: "m-2", title: "Movie m-2" })],
                mutationEventId: 41,
                mutationType: "genre_changed",
            }),
        })
        const store = makeStore(api)
        await joinRoom(store, api)
        const fetchDeckMock = vi.mocked(api.fetchDeck)
        fetchDeckMock.mockClear()

        await store.confirmGenre("Comedy")
        // event_id 41 is now in ignoredEventIds

        // Reconnect clears in-flight but must NOT clear ignoredEventIds.
        store.applySseEvent({ event_type: "session_reset" })

        // Delayed own echo arrives after reconnect with the same id -> still suppressed.
        store.applySseEvent({ event_type: "genre_changed", event_id: 41, genre: "Comedy" })

        expect(fetchDeckMock).not.toHaveBeenCalled()
        expect(store.getState().genre).toBe("Comedy")
    })

    it("clears suppression on session_closed", async () => {
        const api = makeApi({
            fetchDeck: vi.fn().mockResolvedValue([makeCard({ mediaId: "m-1", title: "Movie m-1" })]),
            setGenreChoice: vi.fn().mockResolvedValue({
                deck: [makeCard({ mediaId: "m-2", title: "Movie m-2" })],
                mutationEventId: 41,
                mutationType: "genre_changed",
            }),
        })
        const onExitRoom = vi.fn()
        const store = makeStore(api, onExitRoom)
        await joinRoom(store, api)
        await store.confirmGenre("Comedy")
        const fetchDeckMock = vi.mocked(api.fetchDeck)
        fetchDeckMock.mockClear()

        store.applySseEvent({ event_type: "session_closed", event_id: 1 })
        expect(onExitRoom).toHaveBeenCalled()

        // Ignored ids were cleared, so the same-id echo must refetch.
        store.applySseEvent({ event_type: "genre_changed", event_id: 41, genre: "Comedy" })
        await vi.waitFor(() => expect(fetchDeckMock).toHaveBeenCalledWith(ROOM_CODE))
    })

    it("clears suppression on room exit", async () => {
        const deck = [makeCard({ mediaId: "m-1", title: "Movie m-1" })]
        const api = makeApi({
            fetchDeck: vi.fn().mockResolvedValue(deck),
            setGenreChoice: vi.fn().mockResolvedValue({
                deck,
                mutationEventId: 41,
                mutationType: "genre_changed",
            }),
        })
        const store = makeStore(api)
        await joinRoom(store, api)
        await store.confirmGenre("Comedy")
        const fetchDeckMock = vi.mocked(api.fetchDeck)

        store.onRoomCodeChanged(null)
        store.onRoomCodeChanged(ROOM_CODE)
        await vi.waitFor(() => expect(fetchDeckMock).toHaveBeenCalledTimes(2))
        fetchDeckMock.mockClear()

        // Ignored ids were cleared on exit, so the same-id echo must refetch.
        store.applySseEvent({ event_type: "genre_changed", event_id: 41, genre: "Comedy" })
        await vi.waitFor(() => expect(fetchDeckMock).toHaveBeenCalledWith(ROOM_CODE))
    })
})

describe("RoomSessionStore room-code transitions", () => {
    it("onRoomCodeChanged(null) resets the deck with no fetch", async () => {
        const deck = [makeCard({ mediaId: "m-1", title: "Movie m-1" })]
        const api = makeApi({ fetchDeck: vi.fn().mockResolvedValue(deck) })
        const store = makeStore(api)
        await joinRoom(store, api)
        expect(store.getState().cardDeck).toEqual(deck)
        expect(store.getState().deckLoaded).toBe(true)
        const fetchCallsBefore = vi.mocked(api.fetchDeck).mock.calls.length

        store.onRoomCodeChanged(null)

        expect(store.getState().cardDeck).toEqual([])
        expect(store.getState().deckLoaded).toBe(false)
        expect(api.fetchDeck).toHaveBeenCalledTimes(fetchCallsBefore)
    })

    it("subscribe notifies listeners on state changes", async () => {
        const api = makeApi({ fetchDeck: vi.fn().mockResolvedValue([makeCard({ mediaId: "m-1", title: "Movie m-1" })]) })
        const store = makeStore(api)
        const listener = vi.fn()
        store.subscribe(listener)

        store.onRoomCodeChanged(ROOM_CODE)
        await vi.waitFor(() => expect(listener).toHaveBeenCalled())
    })
})
