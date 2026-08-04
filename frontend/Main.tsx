import React from "react"
import Intro from "./Intro"
import SwipePage from "./SwipePage"
import { useRoomContext } from "./RoomContextProvider"
import { useSSEContext } from "./SSEContextProvider"
import { apiFetch, postJson } from "./api"
import type { JSX } from "react"
import type { CardItem, GenreChangedEvent, HideWatchedChangedEvent } from "./types"
import type { MatchItem } from "./types"
import type { CardDeck } from "./types"
import type { SessionBootstrapResponse } from './types'

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
    const { currentRoomCode, setCurrentRoomCode, setRoomReady, genre, setGenre, hideWatched, setHideWatched } = useRoomContext()
    const [cardDeck, setCardDeck] = React.useState<CardDeck>([])
    const [swipeHistory, setSwipeHistory] = React.useState<CardDeck>([])
    const [matchFound, setMatchFound] = React.useState<boolean>(false)
    const [matchItem, setMatchItem] = React.useState<MatchItem>(DEFAULT_MATCHITEM)
    const [showGenreModal, setShowGenreModal] = React.useState<boolean>(false)
    const { sseData, sseError, isConnected } = useSSEContext()
    const localDeckRefreshSuppressionRef = React.useRef<"genre" | "hide_watched" | null>(null)

    const suppressNextDeckRefresh = React.useCallback((source: "genre" | "hide_watched") => {
        localDeckRefreshSuppressionRef.current = source
        window.setTimeout(() => {
            if (localDeckRefreshSuppressionRef.current === source) {
                localDeckRefreshSuppressionRef.current = null
            }
        }, 1000)
    }, [])

    React.useEffect(() => {    
        switch(sseData?.event_type) {
            case "session_bootstrap":
                const bootstrapData = sseData as SessionBootstrapResponse
                setRoomReady(bootstrapData.ready)
                break
            case "match_found":
                setMatchItem(sseData as MatchItem)
                setMatchFound(true)
                break
            case "genre_changed":
                const genreData = sseData as GenreChangedEvent
                setGenre(genreData.genre as string)
                if (localDeckRefreshSuppressionRef.current === "genre") {
                    localDeckRefreshSuppressionRef.current = null
                    return
                }
                getCardDeck()
                break
            case "hide_watched_changed":
                const watchedData = sseData as HideWatchedChangedEvent
                setHideWatched(watchedData.hide_watched as boolean)
                if (localDeckRefreshSuppressionRef.current === "hide_watched") {
                    localDeckRefreshSuppressionRef.current = null
                    return
                }
                getCardDeck()
                break
            case "session_ready":
                setRoomReady(true)
                break
            case "session_closed":
                setRoomReady(false)
                setCurrentRoomCode(null)
                break
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

    const handleWatchedFilterToggle = React.useCallback( async () => {
        suppressNextDeckRefresh("hide_watched")
        try {
            const res: Response = await postJson(`/room/${currentRoomCode}/watched-filter`, { "hide_watched": !hideWatched })
            if (!res.ok) {
                throw new Error(`Error toggling watched filter: ${res.status} ${res.statusText}`)
            }
            const data = await res.json()
            setCardDeck(data)
            setSwipeHistory([])
            setHideWatched(!hideWatched)
        } catch (err) {
            console.error("Error toggling watched filter", err)
        }
    }, [currentRoomCode, hideWatched, suppressNextDeckRefresh])

    const handleGenreChange = React.useCallback( async () => {
        suppressNextDeckRefresh("genre")
        try {
            const res: Response = await postJson(`/room/${currentRoomCode}/genre`, { genre })
            if (!res.ok) {
                throw new Error(`Error POSTing new genre: ${res.status} ${res.statusText}`)
            }
            const data = await res.json()
            setCardDeck(data)
            setSwipeHistory([])
            setShowGenreModal(false)
        } catch (err) {
            console.error("Error changing genre:", err)
        }
    }, [currentRoomCode, genre, suppressNextDeckRefresh])

    const handleSwipe = React.useCallback(async (
        cardItem: CardItem,
        direction: "left" | "right") => {

        if (!currentRoomCode) {
            console.error("Cannot send swipe without currentRoomCode")
            return
        }

        try {
            const res  = await postJson(`/room/${currentRoomCode}/swipe`, {
                media_id: cardItem.media_id,
                direction,
            })
            if (!res.ok) {
                throw new Error(`Error POSTing swipe: ${res.status} ${res.statusText}`)
            }
            setSwipeHistory(prev => [...prev, cardItem])
            advanceDeck()
        } catch (err) {
            console.error("Error POSTing swipe:", err)
        }

    }, [currentRoomCode, advanceDeck])

    const handleUndo = React.useCallback(async () => {
        const lastSwipe: CardItem = swipeHistory[swipeHistory.length - 1]

        if(!lastSwipe) {
            console.error("Cannot undo without swipe history")
            return
        }

        try {
            const res: Response = await postJson(`/room/${currentRoomCode}/undo`, { media_id: lastSwipe.media_id })
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
            {currentRoomCode && 
                <SwipePage 
                    cardDeck={cardDeck} 
                    onSwipe={handleSwipe} 
                    matchFound={matchFound} 
                    handleMatchClose={handleMatchClose} 
                    matchItem={matchItem} 
                    handleUndo={handleUndo} 
                    handleGenreChange={handleGenreChange}
                    showGenreModal={showGenreModal}
                    setShowGenreModal={setShowGenreModal}
                    handleWatchedFilterToggle={handleWatchedFilterToggle}
                />
            }
        </main>
    )
}