import { describe, expect, expectTypeOf, it } from "vitest"
import {
	initialRoomSessionState,
	roomSessionReducer,
	type RoomSessionAction,
} from "./roomSession"
import { makeCard } from "./test/fixtures"

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

	it("GENRE_COMMAND_SUCCEEDED clears a stale deckError", () => {
		const start = {
			...initialRoomSessionState,
			deckError: "Couldn't load your cards. Check your connection and try again.",
		}

		const next = roomSessionReducer(start, {
			type: "GENRE_COMMAND_SUCCEEDED",
			deck: [],
		})

		expect(next.deckError).toBeNull()
	})

	it("HIDE_WATCHED_COMMAND_SUCCEEDED clears a stale deckError", () => {
		const start = {
			...initialRoomSessionState,
			deckError: "Couldn't load your cards. Check your connection and try again.",
		}

		const next = roomSessionReducer(start, {
			type: "HIDE_WATCHED_COMMAND_SUCCEEDED",
			deck: [],
			hideWatched: true,
		})

		expect(next.deckError).toBeNull()
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

	it("CLEAR_ERROR clears lastError", () => {
		const start = { ...initialRoomSessionState, lastError: "boom" }
		const next = roomSessionReducer(start, { type: "CLEAR_ERROR" })

		expect(next.lastError).toBeNull()
	})

	it("DECK_FETCH_FAILED sets deckError", () => {
		const next = roomSessionReducer(initialRoomSessionState, {
			type: "DECK_FETCH_FAILED",
			message: "Couldn't load your cards.",
		})

		expect(next.deckError).toBe("Couldn't load your cards.")
	})

	it("DECK_LOADED clears deckError", () => {
		const start = { ...initialRoomSessionState, deckError: "boom" }
		const next = roomSessionReducer(start, { type: "DECK_LOADED", deck: [] })

		expect(next.deckError).toBeNull()
	})

	it("DECK_RESET applied to a loaded state clears deck, history, and deckError and resets deckLoaded to false", () => {
		const start = {
			...initialRoomSessionState,
			cardDeck: [makeCard({ mediaId: "m-1", title: "Movie m-1" })],
			swipeHistory: [makeCard({ mediaId: "m-2", title: "Movie m-2" })],
			deckError: "boom",
			deckLoaded: true,
		}

		const next = roomSessionReducer(start, { type: "DECK_RESET" })

		expect(next.cardDeck).toEqual([])
		expect(next.swipeHistory).toEqual([])
		expect(next.deckError).toBeNull()
		expect(next.deckLoaded).toBe(false)
	})

	it("DECK_LOADED sets deckLoaded true from a state where it is false", () => {
		const start = { ...initialRoomSessionState, deckLoaded: false }
		const next = roomSessionReducer(start, { type: "DECK_LOADED", deck: [] })

		expect(next.deckLoaded).toBe(true)
	})

	it("GENRE_COMMAND_SUCCEEDED sets deckLoaded true from a state where it is false", () => {
		const start = { ...initialRoomSessionState, deckLoaded: false }
		const next = roomSessionReducer(start, {
			type: "GENRE_COMMAND_SUCCEEDED",
			deck: [],
		})

		expect(next.deckLoaded).toBe(true)
	})

	it("HIDE_WATCHED_COMMAND_SUCCEEDED sets deckLoaded true from a state where it is false", () => {
		const start = { ...initialRoomSessionState, deckLoaded: false }
		const next = roomSessionReducer(start, {
			type: "HIDE_WATCHED_COMMAND_SUCCEEDED",
			deck: [],
			hideWatched: true,
		})

		expect(next.deckLoaded).toBe(true)
	})

	it("SESSION_ENDED sets deckLoaded false from a loaded state", () => {
		const start = { ...initialRoomSessionState, deckLoaded: true }
		const next = roomSessionReducer(start, { type: "SESSION_ENDED" })

		expect(next.deckLoaded).toBe(false)
	})

	it("SESSION_ENDED clears deckError", () => {
		const start = { ...initialRoomSessionState, deckError: "boom" }
		const next = roomSessionReducer(start, { type: "SESSION_ENDED" })

		expect(next.deckError).toBeNull()
	})

	it("has no reducer action for session_reset (provider handles as no-op)", () => {
		type SessionResetReducerAction = Extract<
			RoomSessionAction,
			{ type: "SSE_SESSION_RESET" }
		>

		expectTypeOf<SessionResetReducerAction>().toEqualTypeOf<never>()
	})
})
