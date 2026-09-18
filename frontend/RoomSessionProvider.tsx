/* eslint-disable react-refresh/only-export-components */

import React from "react"
import { useRoomStateContext, useRoomSetterContext } from "./RoomContextProvider"
import { useSSEContext } from "./SSEContextProvider"
import * as roomApi from "./roomApi"
import { initialRoomSessionState, roomSessionReducer } from "./roomSession"
import { toMatchItem } from "./mediaAdapter"
import type { RoomSessionState } from "./roomSession"
import type { CardItem } from "./types"

export interface RoomSessionContextType {
    state: RoomSessionState
    swipe: (card: CardItem, direction: "left" | "right") => Promise<void>
    undo: () => Promise<void>
    confirmGenre: (genre: string) => Promise<boolean>
    toggleHideWatched: () => Promise<void>
    dismissMatch: () => void
    endSession: () => Promise<void>
    clearError: () => void
    retryDeckFetch: () => Promise<void>
}

const RoomSessionContext = React.createContext<RoomSessionContextType | undefined>(undefined)

export function useRoomSession(): RoomSessionContextType {
    const context = React.useContext(RoomSessionContext)
    if (context === undefined) {
        throw new Error("useRoomSession must be used within a RoomSessionProvider")
    }
    return context
}

const MAX_REGISTERED_EVENT_IDS = 50

export function RoomSessionProvider({ children }: { children: React.ReactNode }) {
    const { currentRoomCode } = useRoomStateContext()
    const { setCurrentRoomCode } = useRoomSetterContext()
    const { sseData, sseError } = useSSEContext()
    const [state, dispatch] = React.useReducer(roomSessionReducer, initialRoomSessionState)
    const stateRef = React.useRef(state)

    // A mutation type whose POST is currently in flight (sent, not yet resolved).
    const inFlightRef = React.useRef<Set<"genre" | "hide_watched">>(new Set())
    // Event IDs of THIS client's own completed mutations, so their SSE echoes
    // can be recognized and their deck refetch suppressed deterministically.
    const ignoredEventIdsRef = React.useRef<Set<number>>(new Set())

    React.useEffect(() => {
        stateRef.current = state
    }, [state])

    // Clear transient suppression state when leaving a room.
    React.useEffect(() => {
        if (!currentRoomCode) {
            inFlightRef.current.clear()
            ignoredEventIdsRef.current.clear()
        }
    }, [currentRoomCode])

    function registerIgnoredEventId(eventId: number): void {
        const ids = ignoredEventIdsRef.current
        ids.add(eventId)
        if (ids.size > MAX_REGISTERED_EVENT_IDS) {
            const oldest = ids.values().next().value
            if (oldest !== undefined) {
                ids.delete(oldest)
            }
        }
    }

    function consumeIgnoredEventId(eventId: number): void {
        ignoredEventIdsRef.current.delete(eventId)
    }

    // Shared deck-fetch code path: dispatches DECK_LOADED on success. On
    // failure, the initial load surfaces DECK_FETCH_FAILED (deck-error panel
    // with retry, issue #340), while a background refetch over an already
    // loaded deck only raises the dismissible banner via COMMAND_FAILED so a
    // transient failure never blanks visible cards.
    const loadDeck = React.useCallback(async (roomCode: string, failureTarget: "panel" | "banner" = "panel") => {
        try {
            const deck = await roomApi.fetchDeck(roomCode)
            dispatch({ type: "DECK_LOADED", deck })
        } catch (err) {
            console.error("Error fetching card deck:", err)
            dispatch(failureTarget === "panel"
                ? {
                    type: "DECK_FETCH_FAILED",
                    message: "Couldn't load your cards. Check your connection and try again."
                }
                : {
                    type: "COMMAND_FAILED",
                    message: "Couldn't refresh your cards. Check your connection and try again."
                })
        }
    }, [])

    // Deck fetch on room join
    React.useEffect(() => {
        if (!currentRoomCode) {
            dispatch({ type: "DECK_RESET" })
            return
        }
        void loadDeck(currentRoomCode)
    }, [currentRoomCode, loadDeck])

    // SSE event -> reducer
    React.useEffect(() => {
        if (!sseData) {
            if (sseError) console.error("SSE error:", sseError)
            return
        }

        function handleSettingsChangedEvent(
            mutationType: "genre" | "hide_watched",
            eventId: number,
            dispatchMirroredState: () => void,
        ): void {
            const isLocalEcho =
                inFlightRef.current.has(mutationType) ||
                ignoredEventIdsRef.current.has(eventId)
            if (isLocalEcho) {
                consumeIgnoredEventId(eventId)
            } else if (currentRoomCode) {
                void loadDeck(currentRoomCode, "banner")
            }
            dispatchMirroredState()
        }

        switch (sseData.event_type) {
            case "session_bootstrap":
                dispatch({ type: "SSE_SESSION_BOOTSTRAP", ready: sseData.ready })
                break
            case "match_found":
                dispatch({ type: "MATCH_FOUND", matchItem: toMatchItem(sseData) })
                break
            case "genre_changed":
                handleSettingsChangedEvent("genre", sseData.event_id, () =>
                    dispatch({ type: "SSE_GENRE_CHANGED", genre: sseData.genre })
                )
                break
            case "hide_watched_changed":
                handleSettingsChangedEvent("hide_watched", sseData.event_id, () =>
                    dispatch({ type: "SSE_HIDE_WATCHED_CHANGED", hideWatched: sseData.hide_watched })
                )
                break
            case "session_ready":
                dispatch({ type: "SSE_SESSION_READY" })
                break
            case "session_closed":
                inFlightRef.current.clear()
                ignoredEventIdsRef.current.clear()
                dispatch({ type: "SSE_SESSION_CLOSED" })
                setCurrentRoomCode(null)
                break
            case "session_reset":
                inFlightRef.current.clear()
                break
            default: {
                const _exhaustive: never = sseData
                return _exhaustive
            }
        }
    }, [sseData, sseError, currentRoomCode, setCurrentRoomCode, loadDeck])

    // commands

    const swipe = React.useCallback(async (card: CardItem, direction: "left" | "right") => {
        if (!currentRoomCode) {
            console.error("Cannot send swipe without currentRoomCode")
            throw new Error("Cannot send swipe without currentRoomCode")
        }
        try {
            await roomApi.postSwipe(currentRoomCode, card.mediaId, direction)
            dispatch({ type: "SWIPE_SUCCEEDED", card })
        } catch (err) {
            console.error("Error POSTing swipe", err)
            dispatch({ type: "COMMAND_FAILED", message: "Couldn't save that swipe. Check your connection and try again." })
            // Re-throw so the caller (the card's commit path) can snap the card
            // back and leave it retryable instead of silently swallowing the
            // failure while the card is already off-screen.
            throw err
        }
    }, [currentRoomCode])

    const undo = React.useCallback(async () => {
        const lastSwipe = stateRef.current.swipeHistory.at(-1)
        if (!lastSwipe) {
            console.error("Cannot undo without swipe history")
            return
        }
        if (!currentRoomCode) {
            console.error("Cannot send swipe without currentRoomCode")
            return
        }
        try {
            await roomApi.undoSwipe(currentRoomCode, lastSwipe.mediaId)
            dispatch({ type: "UNDO_SUCCEEDED", card: lastSwipe })
        } catch (err) {
            console.error("Error undoing swipe", err)
            dispatch({ type: "COMMAND_FAILED", message: "Couldn't undo that swipe. Check your connection and try again." })
        }
    }, [currentRoomCode])

    const confirmGenre = React.useCallback(async (genre: string): Promise<boolean> => {
        if (!currentRoomCode) {
            console.error("Cannot change genre without currentRoomCode")
            return false
        }
        inFlightRef.current.add("genre")
        try {
            const result = await roomApi.setGenreChoice(currentRoomCode, genre)
            dispatch({ type: "GENRE_SELECTED", genre })
            dispatch({ type: "GENRE_COMMAND_SUCCEEDED", deck: result.deck })
            if (result.mutationEventId > 0) registerIgnoredEventId(result.mutationEventId)
            return true
        } catch (err) {
            console.error("Error changing genre", err)
            dispatch({ type: "COMMAND_FAILED", message: "Couldn't change the genre. Check your connection and try again." })
            return false
        } finally {
            inFlightRef.current.delete("genre")
        }
    }, [currentRoomCode])

    const toggleHideWatched = React.useCallback(async () => {
        if (!currentRoomCode) {
            console.error("Cannot toggle watched filter without currentRoomCode")
            return
        }
        const next = !stateRef.current.hideWatched
        inFlightRef.current.add("hide_watched")
        try {
            const result = await roomApi.setWatchedFilter(currentRoomCode, next)
            dispatch({ type: "HIDE_WATCHED_COMMAND_SUCCEEDED", deck: result.deck, hideWatched: next })
            if (result.mutationEventId > 0) registerIgnoredEventId(result.mutationEventId)
        } catch (err) {
            console.error("Error toggling watched filter", err)
            dispatch({ type: "COMMAND_FAILED", message: "Couldn't update the watched filter. Check your connection and try again." })
        } finally {
            inFlightRef.current.delete("hide_watched")
        }
    }, [currentRoomCode])

    const endSession = React.useCallback(async () => {
        if (!currentRoomCode) {
            console.error("Cannot end session without currentRoomCode")
            return
        }
        try {
            await roomApi.quitRoom(currentRoomCode)
            dispatch({ type: "SESSION_ENDED" })
            setCurrentRoomCode(null)
        } catch (err) {
            console.error("Error quitting room", err)
            dispatch({ type: "COMMAND_FAILED", message: "Couldn't end the session. Check your connection and try again." })
        }
    }, [currentRoomCode, setCurrentRoomCode])

    const dismissMatch = React.useCallback(() => dispatch({ type: "MATCH_DISMISSED" }), [])

    const clearError = React.useCallback(() => dispatch({ type: "CLEAR_ERROR" }), [])

    const retryDeckFetch = React.useCallback(async () => {
        if (!currentRoomCode) {
            console.error("Cannot fetch deck without currentRoomCode")
            return
        }
        await loadDeck(currentRoomCode)
    }, [currentRoomCode, loadDeck])

    const value = React.useMemo(() => ({
        state, swipe, undo, confirmGenre, toggleHideWatched, dismissMatch, endSession,
        clearError, retryDeckFetch
    }), [state, swipe, undo, confirmGenre, toggleHideWatched, dismissMatch, endSession,
        clearError, retryDeckFetch])

    return <RoomSessionContext.Provider value={value}>{children}</RoomSessionContext.Provider>
}
