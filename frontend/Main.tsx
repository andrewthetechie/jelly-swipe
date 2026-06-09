import React from "react"
import Intro from "./Intro"
import SwipePage from "./SwipePage"
import { useRoomContext } from "./RoomContextProvider"
import { apiFetch } from "./api"
import type { JSX } from "react"
import type { CardDeck } from "./types"

type RoomStatusResponse = {
    ready: boolean
    genre?: string | null
    solo?: boolean | null
    hide_watched?: boolean | null
}

// joint session needs loading page until ready status is true, solo session can go straight to swipe page

export default function Main(): JSX.Element {
    const { currentRoomCode } = useRoomContext()
    const [cardDeck, setCardDeck] = React.useState<CardDeck>([])

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