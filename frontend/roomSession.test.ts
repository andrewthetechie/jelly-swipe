import React from "react"
import { act, renderHook, waitFor } from "@testing-library/react"
import { expectTypeOf, vi } from "vitest"
import {
	EMPTY_MATCH_ITEM,
	initialRoomSessionState,
	roomSessionReducer,
	type RoomSessionAction,
} from "./roomSession"
import type { MutationChangeResult } from "./types"
import { RoomContextProvider, useRoomSetterContext } from "./RoomContextProvider"
import { RoomSessionProvider, useRoomSession } from "./RoomSessionProvider"
import { useSSEContext, type SSEContextType } from "./SSEContextProvider"
import * as roomApi from "./roomApi"
import { makeCard } from "./test/fixtures"

vi.mock("./roomApi", () => ({
	fetchDeck: vi.fn(),
	postSwipe: vi.fn(),
	undoSwipe: vi.fn(),
	setGenreChoice: vi.fn(),
	setWatchedFilter: vi.fn(),
	quitRoom: vi.fn(),
}))

vi.mock("./SSEContextProvider", () => ({
	useSSEContext: vi.fn(),
}))

const ROOM_CODE = "1234"

let mockSSEContext: SSEContextType

function RoomCodeInitializer({ roomCode }: { roomCode: string }) {
	const { setCurrentRoomCode } = useRoomSetterContext()

	React.useEffect(() => {
		setCurrentRoomCode(roomCode)
	}, [roomCode, setCurrentRoomCode])

	return null
}

function makeWrapper(roomCode = ROOM_CODE) {
	return function Wrapper({ children }: { children: React.ReactNode }) {
		return React.createElement(
			RoomContextProvider,
			null,
			React.createElement(RoomCodeInitializer, { roomCode }),
			React.createElement(RoomSessionProvider, null, children),
		)
	}
}

async function waitForDeckLoad(
	hook: { result: { current: ReturnType<typeof useRoomSession> } },
	expectedDeckSize: number,
) {
	const fetchDeckMock = vi.mocked(roomApi.fetchDeck)

	await waitFor(() => {
		expect(fetchDeckMock).toHaveBeenCalledWith(ROOM_CODE)
		expect(fetchDeckMock).toHaveBeenCalledTimes(1)
	})

	await waitFor(() => {
		// This wait ensures reducer updates from fetch resolution have flushed.
		expect(hook.result.current.state.cardDeck).toHaveLength(expectedDeckSize)
	})
}

function emitSSE(
	hook: { result: { current: ReturnType<typeof useRoomSession> } },
	event: NonNullable<SSEContextType["sseData"]>
) {
	mockSSEContext = { sseData: event, sseError: null, isConnected: true }
	vi.mocked(useSSEContext).mockImplementation(() => mockSSEContext)
	// Force the provider to re-render to it re-reads the context and its SSE effect runs.
	act(() => { hook.result.current.dismissMatch() })
}

describe("roomSession reducer and utils", () => {
	it("SSE_SESSION_BOOTSTRAP sets roomReady from the bootstrap event", () => {
		const next = roomSessionReducer(initialRoomSessionState, {
			type: "SSE_SESSION_BOOTSTRAP",
			ready: true,
		})

		expect(next.roomReady).toBe(true)
	})

	it("SSE_GENRE_CHANGED updates genre and clears pendingDeckRefresh genre flag", () => {
		const start = {
			...initialRoomSessionState,
			genre: "Action",
		}

		const next = roomSessionReducer(start, {
			type: "SSE_GENRE_CHANGED",
			genre: "Comedy",
		})

		expect(next.genre).toBe("Comedy")
	})

	it("SSE_HIDE_WATCHED_CHANGED updates flag and clears pending hide_watched refresh", () => {
		const start = {
			...initialRoomSessionState,
			hideWatched: false,
		}

		const next = roomSessionReducer(start, {
			type: "SSE_HIDE_WATCHED_CHANGED",
			hideWatched: true,
		})

		expect(next.hideWatched).toBe(true)
	})

	it("SSE_SESSION_READY sets roomReady true", () => {
		const next = roomSessionReducer(initialRoomSessionState, {
			type: "SSE_SESSION_READY",
		})

		expect(next.roomReady).toBe(true)
	})

	it("SSE_SESSION_CLOSED sets roomReady false", () => {
		const start = { ...initialRoomSessionState, roomReady: true }
		const next = roomSessionReducer(start, {
			type: "SSE_SESSION_CLOSED",
		})

		expect(next.roomReady).toBe(false)
	})

	it("has no reducer action for session_reset (provider handles as no-op)", () => {
		type SessionResetReducerAction = Extract<
			RoomSessionAction,
			{ type: "SSE_SESSION_RESET" }
		>

		expectTypeOf<SessionResetReducerAction>().toEqualTypeOf<never>()
	})
})

describe("RoomSessionProvider commands", () => {
	beforeEach(() => {
		vi.clearAllMocks()
		mockSSEContext = { sseData: null, sseError: null, isConnected: true }
		vi.mocked(useSSEContext).mockImplementation(() => mockSSEContext)
		vi.mocked(roomApi.fetchDeck).mockResolvedValue([])
	})

	it("swipe success appends history and pops the deck", async () => {
		const first = makeCard({ mediaId: "m-1", title: "Movie m-1" })
		const second = makeCard({ mediaId: "m-2", title: "Movie m-2" })
		vi.mocked(roomApi.fetchDeck).mockResolvedValue([first, second])
		vi.mocked(roomApi.postSwipe).mockResolvedValue()

		const hook = renderHook(() => useRoomSession(), { wrapper: makeWrapper() })
		await waitForDeckLoad(hook, 2)

		await act(async () => {
			await hook.result.current.swipe(first, "right")
		})

		expect(roomApi.postSwipe).toHaveBeenCalledWith(ROOM_CODE, "m-1", "right")
		expect(hook.result.current.state.swipeHistory).toEqual([first])
		expect(hook.result.current.state.cardDeck).toEqual([second])
	})

	it("swipe failure sets lastError and leaves deck untouched", async () => {
		const first = makeCard({ mediaId: "m-1", title: "Movie m-1" })
		const second = makeCard({ mediaId: "m-2", title: "Movie m-2" })
		vi.mocked(roomApi.fetchDeck).mockResolvedValue([first, second])
		vi.mocked(roomApi.postSwipe).mockRejectedValue(new Error("swipe failed"))
		const errorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined)

		const hook = renderHook(() => useRoomSession(), { wrapper: makeWrapper() })
		await waitForDeckLoad(hook, 2)

		await act(async () => {
			await hook.result.current.swipe(first, "left")
		})

		expect(hook.result.current.state.cardDeck).toEqual([first, second])
		expect(hook.result.current.state.swipeHistory).toEqual([])
		expect(hook.result.current.state.lastError).toContain("swipe failed")
		expect(errorSpy).toHaveBeenCalled()
	})

	it("undo with empty history logs error and does not call API", async () => {
		const first = makeCard({ mediaId: "m-1", title: "Movie m-1" })
		vi.mocked(roomApi.fetchDeck).mockResolvedValue([first])
		const errorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined)

		const hook = renderHook(() => useRoomSession(), { wrapper: makeWrapper() })
		await waitForDeckLoad(hook, 1)

		await act(async () => {
			await hook.result.current.undo()
		})

		expect(roomApi.undoSwipe).not.toHaveBeenCalled()
		expect(errorSpy).toHaveBeenCalledWith("Cannot undo without swipe history")
		expect(hook.result.current.state.cardDeck).toEqual([first])
	})

	it("undo success restores the card to the deck front", async () => {
		const first = makeCard({ mediaId: "m-1", title: "Movie m-1" })
		const second = makeCard({ mediaId: "m-2", title: "Movie m-2" })
		vi.mocked(roomApi.fetchDeck).mockResolvedValue([first, second])
		vi.mocked(roomApi.postSwipe).mockResolvedValue()
		vi.mocked(roomApi.undoSwipe).mockResolvedValue()

		const hook = renderHook(() => useRoomSession(), { wrapper: makeWrapper() })
		await waitForDeckLoad(hook, 2)

		await act(async () => {
			await hook.result.current.swipe(first, "right")
		})

		await act(async () => {
			await hook.result.current.undo()
		})

		expect(roomApi.undoSwipe).toHaveBeenCalledWith(ROOM_CODE, "m-1")
		expect(hook.result.current.state.cardDeck).toEqual([first, second])
		expect(hook.result.current.state.swipeHistory).toEqual([])
	})

	it("confirmGenre success replaces deck, clears history, and sets pending genre refresh", async () => {
		const first = makeCard({ mediaId: "m-1", title: "Movie m-1" })
		const second = makeCard({ mediaId: "m-2", title: "Movie m-2" })
		const refreshedDeck = [makeCard({ mediaId: "m-3", title: "Movie m-3" })]
		vi.mocked(roomApi.fetchDeck).mockResolvedValue([first, second])
		vi.mocked(roomApi.postSwipe).mockResolvedValue()
		vi.mocked(roomApi.setGenreChoice).mockResolvedValue({ 
			deck: refreshedDeck, 
			mutationEventId: 5, 
			mutationType: "genre_changed"
		})

		const hook = renderHook(() => useRoomSession(), { wrapper: makeWrapper() })
		await waitForDeckLoad(hook, 2)

		await act(async () => {
			await hook.result.current.swipe(first, "left")
		})

		act(() => {
			hook.result.current.selectGenre("Comedy")
		})

		await act(async () => {
			await hook.result.current.confirmGenre()
		})

		expect(roomApi.setGenreChoice).toHaveBeenCalledWith(ROOM_CODE, "Comedy")
		expect(hook.result.current.state.cardDeck).toEqual(refreshedDeck)
		expect(hook.result.current.state.swipeHistory).toEqual([])
	})

	it("toggleHideWatched uses current state value (no stale closure)", async () => {
		const initialDeck = [makeCard({ mediaId: "m-1", title: "Movie m-1" })]
		vi.mocked(roomApi.fetchDeck).mockResolvedValue(initialDeck)
		vi.mocked(roomApi.setWatchedFilter).mockResolvedValue({
			deck: initialDeck, 
			mutationEventId: 6, 
			mutationType: "hide_watched_changed"
		})

		const hook = renderHook(() => useRoomSession(), { wrapper: makeWrapper() })
		await waitForDeckLoad(hook, 1)

		await act(async () => {
			await hook.result.current.toggleHideWatched()
		})

		await act(async () => {
			await hook.result.current.toggleHideWatched()
		})

		expect(roomApi.setWatchedFilter).toHaveBeenNthCalledWith(1, ROOM_CODE, true)
		expect(roomApi.setWatchedFilter).toHaveBeenNthCalledWith(2, ROOM_CODE, false)
		expect(hook.result.current.state.hideWatched).toBe(false)
	})

	it("endSession success dispatches SESSION_ENDED reset", async () => {
		const first = makeCard({ mediaId: "m-1", title: "Movie m-1" })
		const second = makeCard({ mediaId: "m-2", title: "Movie m-2" })
		vi.mocked(roomApi.fetchDeck).mockResolvedValue([first, second])
		vi.mocked(roomApi.postSwipe).mockResolvedValue()
		vi.mocked(roomApi.setWatchedFilter).mockResolvedValue({ deck: [second], mutationEventId: 6, mutationType: "hide_watched_changed" })
		vi.mocked(roomApi.quitRoom).mockResolvedValue({ status: "ok" })

		const hook = renderHook(() => useRoomSession(), { wrapper: makeWrapper() })
		await waitForDeckLoad(hook, 2)

		await act(async () => {
			await hook.result.current.swipe(first, "right")
		})

		await act(async () => {
			await hook.result.current.toggleHideWatched()
		})

		await act(async () => {
			await hook.result.current.endSession()
		})

		expect(roomApi.quitRoom).toHaveBeenCalledWith(ROOM_CODE)
		expect(hook.result.current.state.roomReady).toBe(false)
		expect(hook.result.current.state.hideWatched).toBe(false)
		expect(hook.result.current.state.cardDeck).toEqual([])
		expect(hook.result.current.state.swipeHistory).toEqual([])
		expect(hook.result.current.state.matchFound).toBe(false)
		expect(hook.result.current.state.matchItem).toEqual(EMPTY_MATCH_ITEM)
	})
})

describe("SSE suppression (event id correlation)", () => {
	beforeEach(() => {
		vi.clearAllMocks()
		mockSSEContext = { sseData: null, sseError: null, isConnected: true }
		vi.mocked(useSSEContext).mockImplementation(() => mockSSEContext)
	})

	it("suppresses own genre echo by registered event id and updates mirrored genre", async () => {
		const genreDeck = [makeCard({ mediaId: "m-1", title: "Movie m-1" })]
		vi.mocked(roomApi.fetchDeck).mockResolvedValue(genreDeck)
		vi.mocked(roomApi.setGenreChoice).mockResolvedValue({
			deck: [makeCard({ mediaId: "m-2", title: "Movie m-2" })],
			mutationEventId: 41,
			mutationType: "genre_changed"
		})

		const hook = renderHook(() => useRoomSession(), { wrapper: makeWrapper() })
		await waitForDeckLoad(hook, 1)
		vi.mocked(roomApi.fetchDeck).mockClear()

		act(() => { hook.result.current.selectGenre("Comedy") })
		await act(async () => { await hook.result.current.confirmGenre() })

		// Its own echo arrives with the same event_id -> no refetch.
		emitSSE(hook, { event_type: "genre_changed", event_id: 41, genre: "Comedy"} )

		expect(roomApi.fetchDeck).not.toHaveBeenCalled()
		expect(hook.result.current.state.genre).toBe("Comedy")
	})

	it("refetches deck on a remote genre echo (unrelated event id, nothing in flight)", async () => {                                                        
		const genreDeck = [makeCard({ mediaId: "m-1", title: "Movie m-1" })]                                                                                 
		vi.mocked(roomApi.fetchDeck).mockResolvedValue(genreDeck)                                                                                            
																																							
		const hook = renderHook(() => useRoomSession(), { wrapper: makeWrapper() })                                                                          
		await waitForDeckLoad(hook, 1)                                                                                                                       
		vi.mocked(roomApi.fetchDeck).mockClear()                                                                                                             
																																							
		emitSSE(hook, { event_type: "genre_changed", event_id: 99, genre: "Comedy" })                                                                        
																																							
		await waitFor(() => expect(roomApi.fetchDeck).toHaveBeenCalledWith(ROOM_CODE))                                                                       
		expect(hook.result.current.state.genre).toBe("Comedy")                                                                                               
	})                                                                                                                                                       
																																							
	it("suppresses own echo arriving before the POST resolves, then still honors a later remote change", async () => {                                       
		const deckA = [makeCard({ mediaId: "m-1", title: "Movie m-1" })]                                                                                     
		vi.mocked(roomApi.fetchDeck).mockResolvedValue(deckA)                                                                                                
																																							
		let release: (r: MutationChangeResult) => void                                                                                                       
		const genrePromise = new Promise<MutationChangeResult>((res) => { release = res })                                                                   
		vi.mocked(roomApi.setGenreChoice).mockImplementation(() => genrePromise)                                                                             
																																							
		const hook = renderHook(() => useRoomSession(), { wrapper: makeWrapper() })                                                                          
		await waitForDeckLoad(hook, 1)                                                                                                                       
		vi.mocked(roomApi.fetchDeck).mockClear()                                                                                                             
																																							
		act(() => { hook.result.current.selectGenre("Comedy") })                                                                                             
																																							
		let confirmPromise: Promise<void>                                                                                                                    
		act(() => { confirmPromise = hook.result.current.confirmGenre() })                                                                                   
																																							
		// Own echo arrives while the POST is still in flight -> suppressed, no refetch.                                                                     
		emitSSE(hook, { event_type: "genre_changed", event_id: 50, genre: "Comedy" })                                                                        
		expect(roomApi.fetchDeck).not.toHaveBeenCalled()                                                                                                     
																																							
		// POST resolves.                                                                                                                                    
		await act(async () => {                                                                                                                              
			release!({ deck: [makeCard({ mediaId: "m-2", title: "Movie m-2" })], mutationEventId: 60, mutationType: "genre_changed" })                       
			await confirmPromise!                                                                                                                            
		})                                                                                                                                                   
																																							
		vi.mocked(roomApi.fetchDeck).mockClear()                                                                                                             
																																							
		// A later remote change must refetch (no stuck suppression).                                                                                        
		emitSSE(hook, { event_type: "genre_changed", event_id: 200, genre: "Drama" })                                                                        
		await waitFor(() => expect(roomApi.fetchDeck).toHaveBeenCalledWith(ROOM_CODE))                                                                       
	})                                                                                                                                                       
																																							
	it("does not leave stale suppression after a failed mutation", async () => {                                                                             
		const deckA = [makeCard({ mediaId: "m-1", title: "Movie m-1" })]                                                                                     
		vi.mocked(roomApi.fetchDeck).mockResolvedValue(deckA)                                                                                                
		vi.mocked(roomApi.setWatchedFilter).mockRejectedValue(new Error("boom"))                                                                             
		const errorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined)                                                                      
																																							
		const hook = renderHook(() => useRoomSession(), { wrapper: makeWrapper() })                                                                          
		await waitForDeckLoad(hook, 1)                                                                                                                       
		vi.mocked(roomApi.fetchDeck).mockClear()                                                                                                             
																																							
		await act(async () => { await hook.result.current.toggleHideWatched() })                                                                             
		expect(hook.result.current.state.lastError).toContain("boom")                                                                                        
																																							
		// A remote hide_watched change must still refetch.                                                                                                  
		emitSSE(hook, { event_type: "hide_watched_changed", event_id: 77, hide_watched: true })                                                              
		await waitFor(() => expect(roomApi.fetchDeck).toHaveBeenCalledWith(ROOM_CODE))                                                                       
		expect(errorSpy).toHaveBeenCalled()                                                                                                                  
	})              
})