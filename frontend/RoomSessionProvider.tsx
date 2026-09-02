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
    selectGenre: (genre: string) => void
    confirmGenre: () => Promise<void>
    toggleHideWatched: () => Promise<void>
    dismissMatch: () => void
    endSession: () => Promise<void>
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

    // Deck fetch on room join
    React.useEffect(() => {
        if (!currentRoomCode) {
            dispatch({ type: "DECK_LOADED", deck: [] })
            return
        }
        roomApi.fetchDeck(currentRoomCode)
            .then((deck) => dispatch({ type: "DECK_LOADED", deck }))
            .catch((err) => console.error("Error fetching card deck:", err))
    }, [currentRoomCode])

    // SSE event -> reducer
    React.useEffect(() => {
        if (!sseData) {
            if (sseError) console.error("SSE error:", sseError)
            return
        }
        switch (sseData.event_type) {
            case "session_bootstrap":
                dispatch({ type: "SSE_SESSION_BOOTSTRAP", ready: sseData.ready })
                break
            case "match_found":
                dispatch({ type: "MATCH_FOUND", matchItem: toMatchItem(sseData) })
                break
            case "genre_changed": {
                const isLocalEcho = 
                    inFlightRef.current.has("genre") ||
                    ignoredEventIdsRef.current.has(sseData.event_id)
                if (isLocalEcho) {
                    consumeIgnoredEventId(sseData.event_id)
                } else if (currentRoomCode) {
                    roomApi.fetchDeck(currentRoomCode)
                        .then((deck) => dispatch({ type: "DECK_LOADED", deck }))
                        .catch((err) => console.error("Error fetching card deck:", err))
                }
                dispatch({ type: "SSE_GENRE_CHANGED", genre: sseData.genre })
                break
            }
            case "hide_watched_changed": {
                const isLocalEcho = 
                    inFlightRef.current.has("hide_watched") ||
                    ignoredEventIdsRef.current.has(sseData.event_id)
                if (isLocalEcho) {
                    consumeIgnoredEventId(sseData.event_id)
                } else if (currentRoomCode) {
                    roomApi.fetchDeck(currentRoomCode)
                        .then((deck) => dispatch({ type: "DECK_LOADED", deck }))
                        .catch((err) => console.error("Error fetching card deck:", err))
                }
                dispatch({ type: "SSE_HIDE_WATCHED_CHANGED", hideWatched: sseData.hide_watched })
                break
            }
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
    }, [sseData, sseError, currentRoomCode, setCurrentRoomCode])

    // commands

    const swipe = React.useCallback(async (card: CardItem, direction: "left" | "right") => {
        if (!currentRoomCode) {
            console.error("Cannot send swipe without currentRoomCode")
            return
        }
        try {
            await roomApi.postSwipe(currentRoomCode, card.mediaId, direction)
            dispatch({ type: "SWIPE_SUCCEEDED", card })
        } catch (err) {
            console.error("Error POSTing swipe", err)
            dispatch({ type: "COMMAND_FAILED", message: String(err) })
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
            dispatch({ type: "COMMAND_FAILED", message: String(err) })
        }
    }, [currentRoomCode])

    const confirmGenre = React.useCallback(async () => {
        if (!currentRoomCode) {
            console.error("Cannot change genre without currentRoomCode")
            return
        }
        inFlightRef.current.add("genre")
        try {
            const result = await roomApi.setGenreChoice(currentRoomCode, stateRef.current.genre)
            dispatch({ 
                type: "GENRE_COMMAND_SUCCEEDED",
                deck: result.deck,
                mutationEventId: result.mutationEventId,
            })
            registerIgnoredEventId(result.mutationEventId)
        } catch (err) {
            console.error("Error changing genre", err)
            dispatch({ type: "COMMAND_FAILED", message: String(err) })
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
            dispatch({ 
                type: "HIDE_WATCHED_COMMAND_SUCCEEDED",
                deck: result.deck,
                hideWatched: next,
                mutationEventId: result.mutationEventId,
            })
            registerIgnoredEventId(result.mutationEventId)
        } catch (err) {
            console.error("Error toggling watched filter", err)
            dispatch({ type: "COMMAND_FAILED", message: String(err) })
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
            dispatch({ type: "COMMAND_FAILED", message: String(err) })
        }
    }, [currentRoomCode, setCurrentRoomCode])

    const selectGenre = React.useCallback((genre: string) => dispatch({ type: "GENRE_SELECTED", genre }), [])
    const dismissMatch = React.useCallback(() => dispatch({ type: "MATCH_DISMISSED" }), [])

    const value = React.useMemo(() => ({
        state, swipe, undo, selectGenre, confirmGenre, toggleHideWatched, dismissMatch, endSession
    }), [state, swipe, undo, selectGenre, confirmGenre, toggleHideWatched, dismissMatch, endSession])

    return <RoomSessionContext.Provider value={value}>{children}</RoomSessionContext.Provider>
}