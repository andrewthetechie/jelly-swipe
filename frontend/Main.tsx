import React from "react"
import Intro from "./Intro"
import SwipePage from "./SwipePage"
import { useRoomContext } from "./RoomContextProvider"
import { useSSEContext } from "./SSEContextProvider"
import { apiFetch } from "./api"
import type { JSX } from "react"
import type { CardItem } from "./types"
import type { MatchItem } from "./types"
import type { CardDeck } from "./types"
import type { SessionBootstrapResponse } from './types'
import type { MatchFoundEvent } from "./types"

const DEFAULT_MATCHITEM: MatchItem = {
    title: null,
    thumb: null,
    media_id: null,
    media_type: null,
    deep_link: null,
    rating: null,
    duration: null,
    year: null
}

export default function Main(): JSX.Element {
    const { currentRoomCode, setCurrentRoomCode, setRoomReady } = useRoomContext()
    const [cardDeck, setCardDeck] = React.useState<CardDeck>([])
    const [swipeHistory, setSwipeHistory] = React.useState<CardDeck>([])
    const [matchFound, setMatchFound] = React.useState<boolean>(false)
    const [matchItem, setMatchItem] = React.useState<MatchItem>(DEFAULT_MATCHITEM)
    const { sseData, sseError, isConnected } = useSSEContext()
    

    React.useEffect(() => {    
        if (sseData && typeof sseData === "object" && sseData !== null) {
            console.log("SSE data received:", sseData)
            if ("event_type" in sseData && sseData.event_type === "session_bootstrap") {
                const bootstrapData = sseData as SessionBootstrapResponse
                console.log("Session bootstrap data:", bootstrapData)
                setRoomReady(bootstrapData.ready)
            }
            if ("event_type" in sseData && sseData.event_type === "match_found") {
                console.log("match found")
                setMatchItem(sseData as MatchItem)
                setMatchFound(true)
            }
            if ("event_type" in sseData && sseData.event_type === "session_ready") {
                setRoomReady(true)
            }
            if("event_type" in sseData && sseData.event_type === "session_closed") {
                setRoomReady(false)
                setCurrentRoomCode(null)
            }
        }

        if (sseError) {
            console.error("SSE error:", sseError)
        }
    }, [sseData, sseError])

    const getCardDeck = React.useCallback(async () => {
        if (!currentRoomCode) {
            setCardDeck([])
            setSwipeHistory([])
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
            setSwipeHistory([])
        } catch (err) {
            console.error("Error fetching card deck:", err)
        }
    }, [currentRoomCode])

    const advanceDeck = React.useCallback(() => {
        setCardDeck(prev => prev.slice(1))
    }, [])

    const handleSwipe = React.useCallback(async (
        cardItem: CardItem,
        direction: "left" | "right") => {

        if (!currentRoomCode) {
            console.error("Cannot send swipe without currentRoomCode")
            return
        }

        try {
            const res  = await apiFetch(`/room/${currentRoomCode}/swipe`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    media_id: cardItem.media_id,
                    direction,
                }),
            })
            if (!res.ok) {
                throw new Error(`Error POSTing swipe: ${res.status} ${res.statusText}`)
            }
            setSwipeHistory(prev => [...prev, cardItem])
            advanceDeck()
        } catch (err) {
            console.error("Error POSTing swipe", err)
        }

    }, [currentRoomCode, advanceDeck])

    const handleUndo = React.useCallback(async () => {
        const lastSwipe: CardItem = swipeHistory[swipeHistory.length - 1]

        if(!lastSwipe) {
            console.error("Cannot undo without swipe history")
            return
        }

        try {
            const res: Response = await apiFetch(`room/${currentRoomCode}/undo`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    media_id: lastSwipe.media_id,
                }),
            })
            if (!res.ok) {
                throw new Error(`Error undoing swipe: ${res.status} ${res.statusText}`)
            }
            setCardDeck(prev => [lastSwipe, ...prev] )
            setSwipeHistory(prev => prev.slice(0, -1))
        } catch (err) {
            console.error("Error undoing swipe:", err)
        }
        
    }, [currentRoomCode, swipeHistory])

    const handleMatchClose = () => {
        setMatchFound(false)
    }

    React.useEffect(() => {
        getCardDeck()
    }, [getCardDeck])

    return (
        <main>
            {!currentRoomCode && <Intro />}
            {currentRoomCode && <SwipePage cardDeck={cardDeck} onSwipe={handleSwipe} matchFound={matchFound} handleMatchClose={handleMatchClose} matchItem={matchItem} handleUndo={handleUndo} />}
        </main>
    )
}