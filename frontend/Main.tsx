import React from "react"
import Intro from "./Intro"
import SwipePage from "./SwipePage"
import { useRoomContext } from "./RoomContextProvider"
import { useSSEContext } from "./SSEContextProvider"
import { apiFetch } from "./api"
import type { JSX } from "react"
import type { CardDeck } from "./types"
import type { SessionBootstrapResponse } from './types'

type RoomStatusResponse = {
    ready: boolean
    genre?: string | null
    solo?: boolean | null
    hide_watched?: boolean | null
}

// joint session need to handle what happens when end_session is initiated by partner

export default function Main(): JSX.Element {
    const { currentRoomCode, setRoomReady } = useRoomContext()
    const [cardDeck, setCardDeck] = React.useState<CardDeck>([])
    const { sseData, sseError, isConnected } = useSSEContext()

    React.useEffect(() => {
            if (sseData && typeof sseData === "object" && sseData !== null) {
                console.log("Received SSE data:", sseData)
                if ("event_type" in sseData && sseData.event_type === "session_bootstrap") {
                    const bootstrapData = sseData as SessionBootstrapResponse
                    console.log("Session bootstrap data:", bootstrapData)
                    setRoomReady(bootstrapData.ready)
                }
                if ("event_type" in sseData && sseData.event_type === "session_ready") {
                    setRoomReady(true)
                }
            }
    
            if (sseError) {
                console.error("SSE error:", sseError)
            }
        }, [sseData, sseError])

    const getCardDeck = React.useCallback(async () => {
        if (!currentRoomCode) {
            setCardDeck([])
            return
        }

        try {
            const res: Response = await apiFetch(`/room/${currentRoomCode}/deck`, {
                method: 'GET',
                headers: {'Content-Type': 'application/json'},
            })
            if (!res.ok) {
                throw new Error(`Error fetching card deck: ${res.status} ${res.statusText}`)
            }

            const data: CardDeck = await res.json()
            setCardDeck(data)
        } catch (err) {
            console.error("Error fetching card deck:", err)
        }
    }, [currentRoomCode])

    React.useEffect(() => {
        getCardDeck()
    }, [getCardDeck])

    return (
        <main>
            {!currentRoomCode && <Intro />}
            {currentRoomCode && <SwipePage cardDeck={cardDeck} refreshCardDeck={getCardDeck} />}
        </main>
    )
}