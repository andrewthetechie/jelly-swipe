import React from "react"
import HostWaiting from "./HostWaiting"
import CardItemView from "./CardItemView"
import MatchFoundModal from "./MatchFoundModal"
import GenreModal from "./GenreModal"
import MatchListModal from "./MatchListModal"
import { useRoomStateContext } from "./RoomContextProvider"
import type { JSX } from "react"
import type { CardItem } from './types'
import { useRoomSession } from "./RoomSessionProvider"

export default function SwipePage(): JSX.Element {
    const { state, swipe, undo, toggleHideWatched, dismissMatch, endSession } = useRoomSession()
    const [dragX, setDragX] = React.useState<number>(0)
    const [showMatchListModal, setShowMatchListModal] = React.useState<boolean>(false)
    const [showGenreModal, setShowGenreModal] = React.useState<boolean>(false)
    const { isSoloMode } = useRoomStateContext()

    const rightOpacity: number =
        dragX > 20
            ? Math.min(Math.abs(dragX) / 200, 1)
            : 0
    const leftOpacity: number =
        dragX < -20
            ? Math.min(Math.abs(dragX) / 200, 1)
            : 0
    // Render at most 3 cards (the top card + ≤2 back cards). Deeper cards are
    // dropped entirely (issue #343) — undo still works because undo re-adds the
    // card to `cardDeck` state and it mounts fresh at the top (see roomSession).
    const visibleCards = state.cardDeck.slice(0, 3).reverse()

    const handleGenreClick = () => {
        setShowGenreModal(prev => !prev)
    }

    const handleMatchListClick = () => {
        setShowMatchListModal(prev => !prev)
    }

    if (state.roomReady) {
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
                            checked={state.hideWatched}
                            onChange={() => {
                                void toggleHideWatched()
                            }}
                        />
                        <span className="slider"></span>

                    </label>
                    <button className="genres" onClick={handleGenreClick}>Genres</button>
                </div>

                <div className="swipe-main">
                    <div className="swipe-deck">
                        {visibleCards.map((cardItem: CardItem, index: number) => (
                            <CardItemView
                                key={cardItem.mediaId}
                                cardItem={cardItem}
                                // rendered order is reversed: the last card is the top.
                                stackIndex={visibleCards.length - 1 - index}
                                setDragX={setDragX}
                                zIndex={index}
                                onSwipe={swipe}
                            />
                        ))}
                    </div>

                    <button className="undo-button" onClick={undo}>Undo</button>
                    <p className="card-item-instructions">Tap poster for full details</p>
                </div>

                <div className="swipe-footer">
                    <button className="end-session" onClick={endSession}>End Session</button>
                    <button className="shortlist" onClick={handleMatchListClick}>Shortlist</button>
                </div>

                <div className="glow glow-left" style={{ opacity: leftOpacity }}></div>
                <div className="glow glow-right" style={{ opacity: rightOpacity }}></div>
                {state.matchFound && <MatchFoundModal onClick={dismissMatch} matchItem={state.matchItem} />}
                {showGenreModal && <GenreModal handleGenreClick={handleGenreClick} />}
                {showMatchListModal && <MatchListModal handleMatchListClick={handleMatchListClick} />}
            </>
        )
    } else {
        return <HostWaiting endSession={endSession} />
    }

}
