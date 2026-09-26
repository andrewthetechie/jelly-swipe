/* eslint-disable react-refresh/only-export-components */

import React from "react"
import { useRoomStateContext, useRoomSetterContext } from "./RoomContextProvider"
import { useSSEContext } from "./SSEContextProvider"
import * as roomApi from "./roomApi"
import { RoomSessionStore } from "./roomSessionStore"
import type { RoomSessionStoreDeps } from "./roomSessionStore"
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

interface RoomSessionProviderProps {
    children: React.ReactNode
    /** Injectable api for tests; defaults to the module import so `vi.mock("./roomApi")` suites keep intercepting. */
    api?: RoomSessionStoreDeps["api"]
    /** Injectable initial state for tests. */
    initialState?: RoomSessionState
}

export function RoomSessionProvider({ children, api = roomApi, initialState }: RoomSessionProviderProps) {
    const { currentRoomCode } = useRoomStateContext()
    const { setCurrentRoomCode } = useRoomSetterContext()
    const { sseData, sseError } = useSSEContext()

    // Create the long-lived store once per mount. `onExitRoom` forwards the
    // exit transition to the room setter; `api` defaults to the module import
    // so existing `vi.mock("./roomApi")` suites keep intercepting store calls.
    const [{ store, subscribe, getState }] = React.useState(() => {
        const store = new RoomSessionStore({
            api,
            onExitRoom: () => setCurrentRoomCode(null),
            initialState,
        })
        return {
            store,
            subscribe: (listener: () => void) => store.subscribe(listener),
            getState: () => store.getState(),
        }
    })

    const state = React.useSyncExternalStore(subscribe, getState)

    // Deck fetch on room join / DECK_RESET on exit.
    React.useEffect(() => {
        store.onRoomCodeChanged(currentRoomCode)
    }, [currentRoomCode, store])

    // SSE event -> store, and surface transport errors.
    React.useEffect(() => {
        if (!sseData) {
            if (sseError) store.reportSseError(sseError)
            return
        }
        store.applySseEvent(sseData)
    }, [sseData, sseError, store])

    const value = React.useMemo<RoomSessionContextType>(() => ({
        state,
        swipe: (card, direction) => store.swipe(card, direction),
        undo: () => store.undo(),
        confirmGenre: (genre) => store.confirmGenre(genre),
        toggleHideWatched: () => store.toggleHideWatched(),
        dismissMatch: () => store.dismissMatch(),
        endSession: () => store.endSession(),
        clearError: () => store.clearError(),
        retryDeckFetch: () => store.retryDeckFetch(),
    }), [state, store])

    return <RoomSessionContext.Provider value={value}>{children}</RoomSessionContext.Provider>
}
