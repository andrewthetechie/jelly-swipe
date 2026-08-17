/* eslint-disable react-hooks/set-state-in-effect */

import React from "react"
import Intro from "./Intro"
import SwipePage from "./SwipePage"
import { useRoomStateContext, useRoomSetterContext } from "./RoomContextProvider"
import { useSSEContext } from "./SSEContextProvider"
import type { JSX } from "react"
import type { CardItem, MatchItem, CardDeck } from "./types"
import { fetchDeck, postSwipe, setGenreChoice, setWatchedFilter, undoSwipe } from "./roomApi"

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
    const { currentRoomCode, genre, hideWatched } = useRoomStateContext()
    const { setCurrentRoomCode, setRoomReady, setGenre, setHideWatched } = useRoomSetterContext()
    const [cardDeck, setCardDeck] = React.useState<CardDeck>([])
    const [swipeHistory, setSwipeHistory] = React.useState<CardDeck>([])
    const [matchFound, setMatchFound] = React.useState<boolean>(false)
    const [matchItem, setMatchItem] = React.useState<MatchItem>(DEFAULT_MATCHITEM)
    const [showGenreModal, setShowGenreModal] = React.useState<boolean>(false)
    const { sseData, sseError } = useSSEContext()
    const localDeckRefreshSuppressionRef = React.useRef<"genre" | "hide_watched" | null>(null)

    const suppressNextDeckRefresh = React.useCallback((source: "genre" | "hide_watched") => {
        localDeckRefreshSuppressionRef.current = source
        window.setTimeout(() => {
            if (localDeckRefreshSuppressionRef.current === source) {
                localDeckRefreshSuppressionRef.current = null
            }
        }, 1000)
    }, [])

    const requireRoomCode = React.useCallback((action: string): string | null => {
        if (!currentRoomCode) {
            console.error(`Cannot ${action} without currentRoomCode`)
            return null
        }
        return currentRoomCode
    }, [currentRoomCode])

    const getCardDeck = React.useCallback(async () => {
        if (!currentRoomCode) {
            return
        }

        try {
            const data = await fetchDeck(currentRoomCode)
            setCardDeck(data)
            setSwipeHistory([])
        } catch (err) {
            console.error("Error fetching card deck:", err)
        }
    }, [currentRoomCode])

    React.useEffect(() => {    
        if (!sseData) {
            return
        }

        switch(sseData.event_type) {
            case "session_bootstrap":
                setRoomReady(sseData.ready)
                break
            case "match_found":
                setMatchItem(sseData as MatchItem)
                setMatchFound(true)
                break
            case "genre_changed":
                if (sseData.genre != null) {
                    setGenre(sseData.genre)
                }
                if (localDeckRefreshSuppressionRef.current === "genre") {
                    localDeckRefreshSuppressionRef.current = null
                    return
                }
                getCardDeck()
                break
            case "hide_watched_changed":
                if (sseData.hide_watched != null) {
                    setHideWatched(sseData.hide_watched)
                }
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
            case "session_reset":
                break
            default: {
                const _exhaustive: never = sseData
                return _exhaustive
            }
        }
    }, [sseData, getCardDeck, setCurrentRoomCode, setGenre, setHideWatched, setRoomReady])    

    React.useEffect(() => {
        if (sseError) {
            console.error("SSE error:", sseError);
        }
    }, [sseError])

    const advanceDeck = React.useCallback(() => {
        setCardDeck(prev => prev.slice(1))
    }, [])

    const handleWatchedFilterToggle = React.useCallback( async () => {
        const roomCode = requireRoomCode("toggle watched filter")
        if (!roomCode) return

        suppressNextDeckRefresh("hide_watched")
        try {
            const data = await setWatchedFilter(roomCode, !hideWatched)
            setCardDeck(data)
            setSwipeHistory([])
            setHideWatched(!hideWatched)
        } catch (err) {
            console.error("Error toggling watched filter", err)
        }
    }, [hideWatched, setHideWatched, suppressNextDeckRefresh, requireRoomCode])

    const handleGenreChange = React.useCallback( async () => {
        const roomCode = requireRoomCode("change genre")
        if (!roomCode) return

        suppressNextDeckRefresh("genre")
        try {
            const data = await setGenreChoice(roomCode, genre)
            setCardDeck(data)
            setSwipeHistory([])
            setShowGenreModal(false)
        } catch (err) {
            console.error("Error changing genre:", err)
        }
    }, [genre, suppressNextDeckRefresh, requireRoomCode])

    const handleSwipe = React.useCallback(async (
        cardItem: CardItem,
        direction: "left" | "right") => {

        const roomCode = requireRoomCode("send swipe")
        if (!roomCode) return

        try {
            await postSwipe(roomCode, cardItem.media_id, direction)
            setSwipeHistory(prev => [...prev, cardItem])
            advanceDeck()
        } catch (err) {
            console.error("Error POSTing swipe:", err)
        }

    }, [advanceDeck, requireRoomCode])

    const handleUndo = React.useCallback(async () => {
        const lastSwipe: CardItem = swipeHistory[swipeHistory.length - 1]

        if(!lastSwipe) {
            console.error("Cannot undo without swipe history")
            return
        }

        const roomCode = requireRoomCode("undo last swipe")
        if (!roomCode) return

        try {
            await undoSwipe(roomCode, lastSwipe.media_id)
            setCardDeck(prev => [lastSwipe, ...prev] )
            setSwipeHistory(prev => prev.slice(0, -1))
        } catch (err) {
            console.error("Error undoing swipe:", err)
        }
        
    }, [swipeHistory, requireRoomCode])

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