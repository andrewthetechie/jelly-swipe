import React from "react"
import Intro from "./Intro"
import SwipePage from "./SwipePage"
import { useRoomContext } from "./RoomContextProvider"
import { apiFetch } from "./api"
import type { JSX } from "react"
import type { CardDeck } from "./types"

type RoomStatusResponse = {
    ready: boolean
    genre?: string
    solo?: boolean
    hide_watched?: boolean
}

export default function Main(): JSX.Element {
    const { currentRoomCode } = useRoomContext()
    const [cardDeck, setCardDeck] = React.useState<CardDeck>([])

    React.useEffect(() => {
        async function checkSessionStatus() {
            try {
                const res: Response = await apiFetch(`/room/${currentRoomCode}/status`, {
                    method: 'GET',
                    headers: {'Content-Type': 'application/json'},
                })
                if (res.ok) {
                    const data: RoomStatusResponse = await res.json()
                    console.log("Session status:", data)
                    // If the room does not exist, returns {"ready": false} with no other fields. When ready, the response also includes genre, solo, and hide_watched settings
                }
            } catch (err) {
                console.error("Error fetching session status:", err)
            }
        }

        async function getCardDeck() {
            try {
                const res: Response = await apiFetch(`/room/${currentRoomCode}/deck`, { 
                    method: 'GET',
                    headers: {'Content-Type': 'application/json'},
                })
                if (res.ok) {
                    const data: CardDeck = await res.json()
                    setCardDeck(data)
                }
            } catch (err) {
                console.error("Error fetching card deck:", err)
            }
        }

        // checkSessionStatus()
        getCardDeck()

    }, [currentRoomCode])

    return (
        <main>
            {!currentRoomCode && <Intro />}
            {currentRoomCode && <SwipePage cardDeck={cardDeck} />}
        </main>
    )
}