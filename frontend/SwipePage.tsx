import React from "react"
import HostWaiting from "./HostWaiting"
import CardItemView from "./CardItemView"
import MatchFoundModal from "./MatchFoundModal"
import GenreModal from "./GenreModal"
import { useRoomContext } from "./RoomContextProvider"
import { useSSEContext } from "./SSEContextProvider"
import { apiFetch, apiUrl } from "./api"
import type { JSX } from "react"
import type { CardItem } from './types'
import type { MatchItem } from "./types"
import type { CardDeck } from './types'
import type { SessionBootstrapResponse } from './types'


interface SwipePageProps {
    cardDeck: CardDeck
    onSwipe?: (
        cardItem: CardItem,
        direction: "left" | "right"
    ) => Promise<void>
    matchFound: boolean
    handleMatchClose: () => void
    matchItem: MatchItem
    handleUndo: () => void
    handleGenreChange: () => void
    showGenreModal: boolean
    setShowGenreModal: React.Dispatch<React.SetStateAction<boolean>>
}

export default function SwipePage({ cardDeck, onSwipe, matchFound, handleMatchClose, matchItem, handleUndo, handleGenreChange, showGenreModal, setShowGenreModal }: SwipePageProps): JSX.Element {
    const [dragX, setDragX] = React.useState<number>(0)
    const { currentRoomCode, setCurrentRoomCode, roomReady, setRoomReady, hideWatched, setHideWatched } = useRoomContext()
    const { sseData, sseError, isConnected } = useSSEContext()
    const hideWatchedText = hideWatched ? "Show Watched" : "Hide Watched"
    const hideWatchedClass = hideWatched ? "hide-watched" : ""

    React.useEffect(() => {
        if (sseData && typeof sseData === "object" && sseData !== null) {
            if ("event_type" in sseData && sseData.event_type === "session_bootstrap") {
                const bootstrapData = sseData as SessionBootstrapResponse
                console.log("Session bootstrap data:", bootstrapData)
            }
        }

        if (sseError) {
            console.error("SSE error:", sseError)
        }
    }, [sseData, sseError])

    const rightOpacity: number = 
        dragX > 20
            ? Math.min(Math.abs(dragX) / 200, 1)
            : 0
    const leftOpacity: number = 
        dragX < -20
            ? Math.min(Math.abs(dragX) / 200, 1)
            : 0
    const visibleCards = cardDeck.slice(0, 5).reverse()

    async function handleEndSession() {
        try {
            const res: Response = await apiFetch(`/room/${currentRoomCode}/quit`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
            })
            if (!res.ok) {
                throw new Error(`Error quitting room: ${res.status} ${res.statusText}`)
            }
            
            const quitRoomResponse: { status: string } = await res.json()
            console.log("Session ended", quitRoomResponse)
            setRoomReady(false)
            setCurrentRoomCode(null)
            
        } catch (err) {
            console.error("Error quitting room:", err)
        }
    }

    const handleGenreClick = () => {
        setShowGenreModal(prev => !prev)
    }

    const handleWatchedFilterClick = () => {
        setHideWatched(prev => !prev)
        // need to move hideWatched state to RoomContext before proceeding
        // /room/{code}/watched-filter POST here
    }

    if (roomReady) {
        return (
            <>
                <div className="swipe-header">
                    <div className="mode-badge">Solo</div>
                    <button className={`show-watched ${hideWatchedClass}`} onClick={handleWatchedFilterClick}>{hideWatchedText}</button>
                    <button className="genres" onClick={handleGenreClick}>Genres</button>
                </div>

                <div className="swipe-main">
                    <div className="swipe-deck">
                        {visibleCards.map((cardItem: CardItem, index: number) => (
                            <CardItemView 
                                key={cardItem.media_id}
                                cardItem={cardItem}
                                isTopCard={index === visibleCards.length - 1}
                                setDragX={setDragX}
                                zIndex={index}
                                onSwipe={onSwipe}
                            />
                        ))}
                    </div>

                    <button className="undo-button" onClick={handleUndo}>Undo</button>
                    <p className="card-item-instructions">Tap poster for full details</p>
                </div>

                <div className="swipe-footer">
                    <button className="end-session" onClick={handleEndSession}>End Session</button>
                    <button className="shortlist">Shortlist</button>
                </div>

                <div className="glow glow-left" style={{ opacity: leftOpacity }}></div>
                <div className="glow glow-right" style={{ opacity: rightOpacity }}></div>
                {matchFound && <MatchFoundModal onClick={handleMatchClose} matchItem={matchItem} />}
                {showGenreModal && <GenreModal handleGenreClick={handleGenreClick} handleGenreChange={handleGenreChange} />}
            </>
        )
    } else {
        return <HostWaiting endSession={handleEndSession} />
    }
    
}