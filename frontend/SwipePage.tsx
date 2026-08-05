import React from "react"
import HostWaiting from "./HostWaiting"
import CardItemView from "./CardItemView"
import MatchFoundModal from "./MatchFoundModal"
import GenreModal from "./GenreModal"
import MatchListModal from "./MatchListModal"
import { useRoomStateContext, useRoomSetterContext } from "./RoomContextProvider"
import { postJson } from "./api"
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
    handleWatchedFilterToggle: () => void
}

export default function SwipePage({ cardDeck, onSwipe, matchFound, handleMatchClose, matchItem, handleUndo, handleGenreChange, showGenreModal, setShowGenreModal, handleWatchedFilterToggle }: SwipePageProps): JSX.Element {
    const [dragX, setDragX] = React.useState<number>(0)
    const [showMatchListModal, setShowMatchListModal] = React.useState<boolean>(false)
    const { currentRoomCode, roomReady, hideWatched, isSoloMode } = useRoomStateContext()
    const { setCurrentRoomCode, setRoomReady, setHideWatched } = useRoomSetterContext()

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
            const res: Response = await postJson(`/room/${currentRoomCode}/quit`)
            if (!res.ok) {
                throw new Error(`Error quitting room: ${res.status} ${res.statusText}`)
            }
            
            const quitRoomResponse: { status: string } = await res.json()
            console.log("Session ended", quitRoomResponse)
            setRoomReady(false)
            setHideWatched(false)
            setCurrentRoomCode(null)
            
        } catch (err) {
            console.error("Error quitting room:", err)
        }
    }

    const handleGenreClick = () => {
        setShowGenreModal(prev => !prev)
    }

    const handleMatchListClick = () => {
        setShowMatchListModal(prev => !prev)
    }

    if (roomReady) {
        return (
            <>
                <div className="swipe-header">
                    {isSoloMode && <div className="mode-badge">Solo</div>}
                    <label
                        htmlFor="hideWatched"
                        className="jelly-toggle swipe-toggle"
                        data-testid="watched-toggle"
                    >
                        <span className="hide-watched-span">Hide Watched</span>
                        <input 
                            type="checkbox"
                            id="hideWatched"
                            name="hideWatched"
                            checked={hideWatched}
                            onChange={() => handleWatchedFilterToggle()}
                        />
                        <span className="slider"></span>

                    </label>
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
                    <button className="shortlist" onClick={handleMatchListClick}>Shortlist</button>
                </div>

                <div className="glow glow-left" style={{ opacity: leftOpacity }}></div>
                <div className="glow glow-right" style={{ opacity: rightOpacity }}></div>
                {matchFound && <MatchFoundModal onClick={handleMatchClose} matchItem={matchItem} />}
                {showGenreModal && <GenreModal handleGenreClick={handleGenreClick} handleGenreChange={handleGenreChange} />}
                {showMatchListModal && <MatchListModal handleMatchListClick={handleMatchListClick} />}
            </>
        )
    } else {
        return <HostWaiting endSession={handleEndSession} />
    }
    
}