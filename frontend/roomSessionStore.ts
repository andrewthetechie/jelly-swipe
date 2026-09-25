import { initialRoomSessionState, roomSessionReducer } from "./roomSession"
import { toMatchItem } from "./mediaAdapter"
import type { RoomSessionState } from "./roomSession"
import type { CardItem, CardDeck, MutationChangeResult, SSEEvent } from "./types"

const MAX_REGISTERED_EVENT_IDS = 50

export const GENRE_COMMAND_FAILED_MESSAGE = "Couldn't change the genre. Check your connection and try again."

type MutationType = "genre" | "hide_watched"

export interface RoomSessionApi {
    fetchDeck(roomCode: string): Promise<CardDeck>
    postSwipe(roomCode: string, mediaId: string, direction: "left" | "right"): Promise<void>
    undoSwipe(roomCode: string, mediaId: string): Promise<void>
    setGenreChoice(roomCode: string, genre: string): Promise<MutationChangeResult>
    setWatchedFilter(roomCode: string, hideWatched: boolean): Promise<MutationChangeResult>
    quitRoom(roomCode: string): Promise<{ status: string }>
}

export interface RoomSessionStoreDeps {
    api: RoomSessionApi
    onExitRoom: () => void
    initialState?: RoomSessionState
}

/**
 * Long-lived, plain (non-React) store for the room-session command layer: the
 * reducer, the seven commands, the deck-fetch policy, and mutation-echo
 * suppression. Created once per provider mount and reset on room exit rather
 * than recreated per room, so `ignoredEventIds` survives `session_reset`
 * (reconnect-retention).
 */
export class RoomSessionStore {
    private state: RoomSessionState
    private readonly api: RoomSessionApi
    private readonly onExitRoom: () => void
    private currentRoomCode: string | null = null
    private readonly listeners = new Set<() => void>()

    // A mutation type whose POST is currently in flight (sent, not yet resolved).
    private readonly inFlight = new Set<MutationType>()
    // Event IDs of THIS client's own completed mutations, so their SSE echoes
    // can be recognized and their deck refetch suppressed deterministically.
    private readonly ignoredEventIds = new Set<number>()

    constructor(deps: RoomSessionStoreDeps) {
        this.api = deps.api
        this.onExitRoom = deps.onExitRoom
        this.state = deps.initialState ?? initialRoomSessionState
    }

    getState(): RoomSessionState {
        return this.state
    }

    subscribe(listener: () => void): () => void {
        this.listeners.add(listener)
        return () => {
            this.listeners.delete(listener)
        }
    }

    /** Surface an SSE transport error for logging (mirrors the provider's console.error). */
    reportSseError(err: unknown): void {
        console.error("SSE error:", err)
    }

    private dispatch(action: Parameters<typeof roomSessionReducer>[1]): void {
        this.state = roomSessionReducer(this.state, action)
        this.listeners.forEach((listener) => listener())
    }

    private registerIgnoredEventId(eventId: number): void {
        this.ignoredEventIds.add(eventId)
        if (this.ignoredEventIds.size > MAX_REGISTERED_EVENT_IDS) {
            const oldest = this.ignoredEventIds.values().next().value
            if (oldest !== undefined) {
                this.ignoredEventIds.delete(oldest)
            }
        }
    }

    private consumeIgnoredEventId(eventId: number): void {
        this.ignoredEventIds.delete(eventId)
    }

    // Shared deck-fetch code path: dispatches DECK_LOADED on success. On
    // failure, the initial load surfaces DECK_FETCH_FAILED (deck-error panel
    // with retry, issue #340), while a background refetch over an already
    // loaded deck only raises the dismissible banner via COMMAND_FAILED so a
    // transient failure never blanks visible cards.
    private async loadDeck(roomCode: string, failureTarget: "panel" | "banner" = "panel"): Promise<void> {
        try {
            const deck = await this.api.fetchDeck(roomCode)
            this.dispatch({ type: "DECK_LOADED", deck })
        } catch (err) {
            console.error("Error fetching card deck:", err)
            this.dispatch(failureTarget === "panel"
                ? {
                    type: "DECK_FETCH_FAILED",
                    message: "Couldn't load your cards. Check your connection and try again.",
                }
                : {
                    type: "COMMAND_FAILED",
                    message: "Couldn't refresh your cards. Check your connection and try again.",
                })
        }
    }

    /** Shell entry point: the room code changed. Null resets the deck and clears suppression. */
    onRoomCodeChanged(code: string | null): void {
        this.currentRoomCode = code
        if (!code) {
            this.inFlight.clear()
            this.ignoredEventIds.clear()
            this.dispatch({ type: "DECK_RESET" })
            return
        }
        void this.loadDeck(code)
    }

    private handleSettingsChangedEvent(
        mutationType: MutationType,
        eventId: number,
        dispatchMirroredState: () => void,
    ): void {
        const isLocalEcho =
            this.inFlight.has(mutationType) ||
            this.ignoredEventIds.has(eventId)
        if (isLocalEcho) {
            this.consumeIgnoredEventId(eventId)
        } else if (this.currentRoomCode) {
            void this.loadDeck(this.currentRoomCode, "banner")
        }
        dispatchMirroredState()
    }

    /** Shell entry point: apply an incoming SSE event to the store. */
    applySseEvent(event: SSEEvent): void {
        switch (event.event_type) {
            case "session_bootstrap":
                this.dispatch({ type: "SSE_SESSION_BOOTSTRAP", ready: event.ready })
                break
            case "match_found":
                this.dispatch({ type: "MATCH_FOUND", matchItem: toMatchItem(event) })
                break
            case "genre_changed":
                this.handleSettingsChangedEvent("genre", event.event_id, () =>
                    this.dispatch({ type: "SSE_GENRE_CHANGED", genre: event.genre })
                )
                break
            case "hide_watched_changed":
                this.handleSettingsChangedEvent("hide_watched", event.event_id, () =>
                    this.dispatch({ type: "SSE_HIDE_WATCHED_CHANGED", hideWatched: event.hide_watched })
                )
                break
            case "session_ready":
                this.dispatch({ type: "SSE_SESSION_READY" })
                break
            case "session_closed":
                this.inFlight.clear()
                this.ignoredEventIds.clear()
                this.dispatch({ type: "SSE_SESSION_CLOSED" })
                this.onExitRoom()
                break
            case "session_reset":
                this.inFlight.clear()
                break
            default: {
                const _exhaustive: never = event
                return _exhaustive
            }
        }
    }

    async swipe(card: CardItem, direction: "left" | "right"): Promise<void> {
        if (!this.currentRoomCode) {
            console.error("Cannot send swipe without currentRoomCode")
            throw new Error("Cannot send swipe without currentRoomCode")
        }
        try {
            await this.api.postSwipe(this.currentRoomCode, card.mediaId, direction)
            this.dispatch({ type: "SWIPE_SUCCEEDED", card })
        } catch (err) {
            console.error("Error POSTing swipe", err)
            this.dispatch({ type: "COMMAND_FAILED", message: "Couldn't save that swipe. Check your connection and try again." })
            // Re-throw so the caller (the card's commit path) can snap the card
            // back and leave it retryable instead of silently swallowing the
            // failure while the card is already off-screen.
            throw err
        }
    }

    async undo(): Promise<void> {
        const lastSwipe = this.state.swipeHistory.at(-1)
        if (!lastSwipe) {
            console.error("Cannot undo without swipe history")
            return
        }
        if (!this.currentRoomCode) {
            console.error("Cannot send swipe without currentRoomCode")
            return
        }
        try {
            await this.api.undoSwipe(this.currentRoomCode, lastSwipe.mediaId)
            this.dispatch({ type: "UNDO_SUCCEEDED", card: lastSwipe })
        } catch (err) {
            console.error("Error undoing swipe", err)
            this.dispatch({ type: "COMMAND_FAILED", message: "Couldn't undo that swipe. Check your connection and try again." })
        }
    }

    async confirmGenre(genre: string): Promise<boolean> {
        if (!this.currentRoomCode) {
            console.error("Cannot change genre without currentRoomCode")
            return false
        }
        this.inFlight.add("genre")
        try {
            const result = await this.api.setGenreChoice(this.currentRoomCode, genre)
            this.dispatch({ type: "GENRE_SELECTED", genre })
            this.dispatch({ type: "GENRE_COMMAND_SUCCEEDED", deck: result.deck })
            if (result.mutationEventId > 0) this.registerIgnoredEventId(result.mutationEventId)
            return true
        } catch (err) {
            console.error("Error changing genre", err)
            this.dispatch({ type: "COMMAND_FAILED", message: GENRE_COMMAND_FAILED_MESSAGE })
            return false
        } finally {
            this.inFlight.delete("genre")
        }
    }

    async toggleHideWatched(): Promise<void> {
        if (!this.currentRoomCode) {
            console.error("Cannot toggle watched filter without currentRoomCode")
            return
        }
        const next = !this.state.hideWatched
        this.inFlight.add("hide_watched")
        try {
            const result = await this.api.setWatchedFilter(this.currentRoomCode, next)
            this.dispatch({ type: "HIDE_WATCHED_COMMAND_SUCCEEDED", deck: result.deck, hideWatched: next })
            if (result.mutationEventId > 0) this.registerIgnoredEventId(result.mutationEventId)
        } catch (err) {
            console.error("Error toggling watched filter", err)
            this.dispatch({ type: "COMMAND_FAILED", message: "Couldn't update the watched filter. Check your connection and try again." })
        } finally {
            this.inFlight.delete("hide_watched")
        }
    }

    async endSession(): Promise<void> {
        if (!this.currentRoomCode) {
            console.error("Cannot end session without currentRoomCode")
            return
        }
        try {
            await this.api.quitRoom(this.currentRoomCode)
            this.dispatch({ type: "SESSION_ENDED" })
            this.onExitRoom()
        } catch (err) {
            console.error("Error quitting room", err)
            this.dispatch({ type: "COMMAND_FAILED", message: "Couldn't end the session. Check your connection and try again." })
        }
    }

    dismissMatch(): void {
        this.dispatch({ type: "MATCH_DISMISSED" })
    }

    clearError(): void {
        this.dispatch({ type: "CLEAR_ERROR" })
    }

    async retryDeckFetch(): Promise<void> {
        if (!this.currentRoomCode) {
            console.error("Cannot fetch deck without currentRoomCode")
            return
        }
        await this.loadDeck(this.currentRoomCode)
    }
}
