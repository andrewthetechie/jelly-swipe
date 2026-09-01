
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
    const [lastMessage, setLastMessage] = React.useState<SSEEvent | null>(null)
    const [error, setError] = React.useState<string | null>(null)
    const [isConnected, setIsConnected] = React.useState<boolean>(false)

    const eventSourceRef = React.useRef<EventSource | null>(null)
    const reconnectTimeoutRef = React.useRef<ReturnType<typeof setTimeout> | null>(null)
    const lastSeenEventIdRef = React.useRef<number>(0)
    const connectRef = React.useRef<(() => void) | null>(null)

    const scheduleReconnect = React.useCallback((delayMs: number) => {
        if (reconnectTimeoutRef.current) {
            return
        }

        reconnectTimeoutRef.current = setTimeout(() => {
            reconnectTimeoutRef.current = null
            connectRef.current?.()
        }, delayMs)
    }, [])

    const handleSessionReset = React.useCallback(() => {
        lastSeenEventIdRef.current = 0

        if (eventSourceRef.current) {
            eventSourceRef.current.close()
            eventSourceRef.current = null
        }

        scheduleReconnect(1000)
    }, [scheduleReconnect])

    const connect = React.useCallback(() => {
        if (!url) {
            return
        }

        try {
            if (eventSourceRef.current) {
                eventSourceRef.current.close()
                eventSourceRef.current = null
            }

            const streamUrl = new URL(url, window.location.origin)

            if (lastSeenEventIdRef.current > 0) {
                streamUrl.searchParams.set("after_event_id", String(lastSeenEventIdRef.current))
            }

            const eventSource = new EventSource(streamUrl, { withCredentials: true })
            eventSourceRef.current = eventSource

            eventSource.onopen = () => {
                console.log("SSE connection opened")
                setIsConnected(true)
                setError(null)
            }

            eventSource.onmessage = (e) => {
                if (e.lastEventId) {
                    const eventId = Number.parseInt(e.lastEventId, 10)

                    if (!Number.isNaN(eventId) && eventId > lastSeenEventIdRef.current) {
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

            eventSource.onerror = (e) => {
                console.error("SSE connection error:", e)
                setError("Connection lost. Attempting to reconnect...")
                setIsConnected(false)

                eventSource.close()
                eventSourceRef.current = null

                scheduleReconnect(3000)
            }
        } catch (err) {
            console.error("Error establishing SSE connection:", err)
            setError("Error establishing SSE connection")
        }
    }, [handleSessionReset, scheduleReconnect, url])

    React.useEffect(() => {
        connectRef.current = connect
    }, [connect])

    const disconnect = React.useCallback(() => {
        if (eventSourceRef.current) {
            eventSourceRef.current.close()
            eventSourceRef.current = null
        }

        if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current)
            reconnectTimeoutRef.current = null
        }

        lastSeenEventIdRef.current = 0

        setError(null)
        setLastMessage(null)
        setIsConnected(false)
    }, [])

    React.useEffect(() => {
        if (!url) {
            return
        }

        const establishConnection = () => {
            if (eventSourceRef.current) {
                eventSourceRef.current.close()
                eventSourceRef.current = null
            }

            const streamUrl = new URL(url, window.location.origin)

            if (lastSeenEventIdRef.current > 0) {
                streamUrl.searchParams.set("after_event_id", String(lastSeenEventIdRef.current))
            }

            const eventSource = new EventSource(streamUrl, { withCredentials: true })
            eventSourceRef.current = eventSource

            eventSource.onopen = () => {
                console.log("SSE connection opened")
                setIsConnected(true)
                setError(null)
            }

            eventSource.onmessage = (e) => {
                if (e.lastEventId) {
                    const eventId = Number.parseInt(e.lastEventId, 10)

                    if (!Number.isNaN(eventId) && eventId > lastSeenEventIdRef.current) {
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

            eventSource.onerror = (e) => {
                console.error("SSE connection error:", e)
                setError("Connection lost. Attempting to reconnect...")
                setIsConnected(false)

                eventSource.close()
                eventSourceRef.current = null

                scheduleReconnect(3000)
            }
        }

        establishConnection()

        return () => {
            if (eventSourceRef.current) {
                eventSourceRef.current.close()
                eventSourceRef.current = null
            }

            if (reconnectTimeoutRef.current) {
                clearTimeout(reconnectTimeoutRef.current)
                reconnectTimeoutRef.current = null
            }

            lastSeenEventIdRef.current = 0
        }
    }, [handleSessionReset, scheduleReconnect, url])

    return {
        lastMessage,
        error,
        isConnected,
        connect,
        disconnect,
    }
}