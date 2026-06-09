import React from "react"

export const useSSE = (url: string | null) => {
    const [data, setData] = React.useState<unknown>({}) // Store received data, most recent message
    const [error, setError] = React.useState<unknown>(null) // Store error state
    const [isConnected, setIsConnected] = React.useState<boolean>(false) // Connection status
    const eventSourceRef = React.useRef<EventSource | null>(null) // EventSource object reference - maintains object across re-renders
    const reconnectTimeoutRef = React.useRef<ReturnType<typeof setTimeout> | null>(null) // Reconnection timer reference - for cleanup on component unmount


    // useCallback memoizes function - creates new one only when dependencies change (in this case, url) - prevents unnecessary re-creation of functions on every render
    const connect = React.useCallback(() => {
        if (!url) {
            return
        }

        try {
            // Close existing connection if present
            if (eventSourceRef.current) {
                eventSourceRef.current.close()
            }

            // Create new EventSource object with credentials for authentication
            const eventSource = new EventSource(url, { withCredentials: true })
            eventSourceRef.current = eventSource

            // Event handler for succesful connection
            eventSource.onopen = () => {
                console.log("SSE connection opened")
                setIsConnected(true)
                setError(null)
            }

            // Event handler for message reception - parses incoming data and updates state
            eventSource.onmessage = (e) => {
                try {
                    const parsedData = JSON.parse(e.data)
                    setData(parsedData)
                } catch (parseErr) {
                    console.error("Error parsing SSE data:", parseErr)
                    setError("Error parsing SSE data")
                }
            }

            // Event handler for connection errors
            eventSource.onerror = (e) => {
                console.error("SSE connection error:", e)
                setIsConnected(false)

                if (eventSource.readyState === EventSource.CLOSED) {
                    setError("Connection lost. Attempting to reconnect...")

                    reconnectTimeoutRef.current = setTimeout(() => {
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
        }
        setIsConnected(false)
    }, [])

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
        data,
        error,
        isConnected,
        connect,
        disconnect
    }
}