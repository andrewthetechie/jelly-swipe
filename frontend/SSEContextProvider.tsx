import React from "react"
import { useSSE } from "./useSSE"
import { apiUrl } from "./api"
import { useRoomStateContext } from "./RoomContextProvider"
import type { SSEEvent } from "./types"

export interface SSEContextType {
    sseData: SSEEvent | null
    sseError: string | null
    isConnected: boolean
}

export const SSEContext = React.createContext<SSEContextType | undefined>(undefined)

interface SSEProviderProps {
    children: React.ReactNode
}

export function SSEContextProvider({ children }: SSEProviderProps) {
    const { currentRoomCode } = useRoomStateContext()
    const streamUrl = currentRoomCode ? apiUrl(`/room/${currentRoomCode}/stream`).toString() : null
    
    const { lastMessage: sseData, error: sseError, isConnected } = useSSE(streamUrl)

    return (
        <SSEContext.Provider value={{ sseData, sseError, isConnected }}>
            {children}
        </SSEContext.Provider>
    )
}

export function useSSEContext() {
    const context = React.useContext(SSEContext)
    if (context === undefined) {
        throw new Error("useSSEContext must be used within SSEContextProvider")
    }
    return context
}
