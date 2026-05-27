import React from "react"
import Intro from "./Intro"
import SwipePage from "./SwipePage"
import { RoomContext } from "./App"
import { apiFetch } from "./api"

export default function Main() {
    const { currentRoomCode, setCurrentRoomCode } = React.useContext(RoomContext)
    const [cardDeck, setCardDeck] = React.useState([])

    React.useEffect(() => {
        async function checkSessionStatus() {
            try {
                const res = await apiFetch(`/room/${currentRoomCode}/status`, {
                    method: 'GET',
                    headers: {'Content-Type': 'application/json'},
                })
                if (res.ok) {
                    const data = await res.json()
                    console.log("Session status:", data)
                    // If the room does not exist, returns {"ready": false} with no other fields. When ready, the response also includes genre, solo, and hide_watched settings
                }
            } catch (err) {
                console.error("Error fetching session status:", err)
            }
        }

        async function getCardDeck() {
            try {
                const res = await apiFetch(`/room/${currentRoomCode}/deck`, { 
                    method: 'GET',
                    headers: {'Content-Type': 'application/json'},
                })
                if (res.ok) {
                    const data = await res.json()
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