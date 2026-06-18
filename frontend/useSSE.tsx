import React from "react"
import type { SSEEvent } from "./types"

interface UseSSEReturn {
    lastMessage: SSEEvent | null
    error: string | null
    isConnected: boolean
    connect: () => void
    disconnect: () => void
}

export const useSSE = (url: string | null): UseSSEReturn => {
    const [lastMessage, setLastMessage] = React.useState<SSEEvent | null>(null) // Store received data, most recent message
    const [error, setError] = React.useState<string | null>(null) // Store error state
    const [isConnected, setIsConnected] = React.useState<boolean>(false) // Connection status


    const eventSourceRef = React.useRef<EventSource | null>(null) // EventSource object reference - maintains object across re-renders
    const reconnectTimeoutRef = React.useRef<ReturnType<typeof setTimeout> | null>(null) // Reconnection timer reference - for cleanup on component unmount
    const lastSeenEventIdRef = React.useRef<number>(0)



    // useCallback memoizes function - creates new one only when dependencies change (in this case, url) - prevents unnecessary re-creation of functions on every render
    const connect = React.useCallback(() => {
        if (!url) {
            return
        }

        try {
            // Close existing connection if present
            if (eventSourceRef.current) {
                eventSourceRef.current.close()
                eventSourceRef.current = null
            }

            // Create new EventSource object with credentials for authentication
            const streamUrl = new URL(url, window.location.origin)

            if (lastSeenEventIdRef.current > 0) {
                streamUrl.searchParams.set(
                    "after_event_id",
                    String(lastSeenEventIdRef.current)
                )
            }

            const eventSource = new EventSource(streamUrl, { withCredentials: true })
            eventSourceRef.current = eventSource

            // Event handler for succesful connection
            eventSource.onopen = () => {
                console.log("SSE connection opened")
                setIsConnected(true)
                setError(null)
            }

            // Event handler for message reception - parses incoming data and updates state
            eventSource.onmessage = (e) => {
                if (e.lastEventId) {
                    const eventId = Number.parseInt(e.lastEventId, 10)

                    if (
                        !Number.isNaN(eventId) &&
                        eventId > lastSeenEventIdRef.current
                    ) {
                        lastSeenEventIdRef.current = eventId
                    }
                }
                
                try {
                    const parsedData: SSEEvent = JSON.parse(e.data)

                    if (parsedData.event_type === "session_reset") {
                        handleSessionReset()
                        return
                    }
                    
                    setLastMessage(parsedData)
                } catch (parseErr) {
                    console.error("Error parsing SSE data:", parseErr)
                    setError("Error parsing SSE data")
                }
            }

            // Event handler for connection errors
            eventSource.onerror = (e) => {
                console.error("SSE connection error:", e)
                setIsConnected(false)

                eventSource.close()
                eventSourceRef.current = null

                if (!reconnectTimeoutRef.current) {
                    setError("Connection lost. Attempting to reconnect...")
                    reconnectTimeoutRef.current = setTimeout(() => {
                        reconnectTimeoutRef.current = null
                        connect()
                    }, 3000) // Attempt to reconnect after 3 seconds
                }
                
            }
        } catch (err) {
            // Handle EventSource creation errors (e.g., invalid URL, browser incompatibility)
            console.error("Error establishing SSE connection:", err)
            setError("Error establishing SSE connection")
        }
    }, [url])

    // Disconnect function - closes existing connection and clears reconnection timer
    const disconnect = React.useCallback(() => {
        // Close EventSource connection if it exists
        if (eventSourceRef.current) {
            eventSourceRef.current.close()
            eventSourceRef.current = null
        }

        // Cancel reconnection timer if running
        if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current)
            reconnectTimeoutRef.current = null
        }

        lastSeenEventIdRef.current = 0

        setError(null)
        setLastMessage(null)
        setIsConnected(false)
    }, [])

    const handleSessionReset = React.useCallback(() => {
        lastSeenEventIdRef.current = 0

        if (eventSourceRef.current) {
            eventSourceRef.current.close()
            eventSourceRef.current = null
        }

        if (!reconnectTimeoutRef.current) {
            reconnectTimeoutRef.current = setTimeout(() => {
                reconnectTimeoutRef.current = null
                connect()
            }, 1000)
        }
        reconnectTimeoutRef.current = setTimeout(() => {
            reconnectTimeoutRef.current = null
            connect()
        }, 1000)
    }, [connect])

    React.useEffect(() => {
        if (!url) {
            disconnect()
            return
        }

        connect()

        return () => {
            disconnect()
        }
    }, [url, connect, disconnect])

    return {
        lastMessage,
        error,
        isConnected,
        connect,
        disconnect
    }
}