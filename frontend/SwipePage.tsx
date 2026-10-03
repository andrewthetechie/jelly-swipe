import React from "react"
import HostWaiting from "./HostWaiting"
import SwipeDeck, { type SwipeDeckHandle } from "./SwipeDeck"
import MatchFoundModal from "./MatchFoundModal"
import GenreModal from "./GenreModal"
import MatchListModal from "./MatchListModal"
import { useRoomStateContext } from "./RoomContextProvider"
import type { JSX } from "react"
import { useRoomSession } from "./RoomSessionProvider"
import { usePosterPrefetch } from "./usePosterPrefetch"
import { useSwipeDeckKeyboard } from "./useSwipeDeckKeyboard"

export default function SwipePage(): JSX.Element {
    const { state, swipe, undo, toggleHideWatched, dismissMatch, endSession, clearError, retryDeckFetch } = useRoomSession()
    const [showMatchListModal, setShowMatchListModal] = React.useState<boolean>(false)
    const [showGenreModal, setShowGenreModal] = React.useState<boolean>(false)
    const { isSoloMode } = useRoomStateContext()

    // Prefetch the next 3 cards beyond the rendered 3-card window (issue #350)
    // so their posters are in cache by the time they reach the top. `slice`
    // naturally yields fewer entries on a short deck; no guard needed.
    usePosterPrefetch(state.cardDeck.slice(3, 6).map((c) => c.posterUrl))

    // Imperative handle to the deck, so the Nope/Like buttons and keyboard
    // handler drive the same commit/toggle path a drag uses.
    const deckRef = React.useRef<SwipeDeckHandle | null>(null)

    // Keyboard swipe support (issue #344): Left/Right swipe, Up/Enter flip.
    // Guards live in the useSwipeDeckKeyboard hook (issue #419); the folded
    // `enabled` boolean below is observably equivalent to today's per-guard
    // early returns.
    useSwipeDeckKeyboard({
        enabled: state.roomReady && !state.matchFound && !showGenreModal && !showMatchListModal,
        onSwipe: React.useCallback((direction) => deckRef.current?.commit(direction), []),
        onToggleDetails: React.useCallback(() => deckRef.current?.toggleDetails(), []),
    })

    const openGenreModal = () => {
        setShowGenreModal(true)
    }

    const closeGenreModal = () => {
        setShowGenreModal(false)
    }

    const openMatchListModal = () => {
        setShowMatchListModal(true)
    }

    const closeMatchListModal = () => {
        setShowMatchListModal(false)
    }

    const errorBanner = state.lastError && (
        <div className="error-banner" role="alert">
            <span>{state.lastError}</span>
            <button className="error-dismiss" aria-label="Dismiss error" onClick={clearError}>×</button>
        </div>
    )

    if (state.roomReady) {
        return (
            <>
                {errorBanner}
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
                    <button className="btn-secondary genres" onClick={openGenreModal}>Genres</button>
                </div>

                <div className="swipe-main">
                    <div className="swipe-deck">
                        {/* The deck module stays mounted across the deck-error/deck-end
                            empty states so a just-committed leaving card keeps flying
                            over them (issue #360); it renders the empty-state node in
                            place of the stack when the deck empties. */}
                        <SwipeDeck
                            ref={deckRef}
                            deck={state.cardDeck}
                            onSave={swipe}
                            emptyState={
                                state.deckError && state.cardDeck.length === 0 ? (
                                    <div className="deck-error" role="alert">
                                        <p>{state.deckError}</p>
                                        <button className="retry-deck" onClick={retryDeckFetch}>Try again</button>
                                    </div>
                                ) : state.deckLoaded && state.cardDeck.length === 0 ? (
                                    <div className="deck-end">
                                        <p>That's everything for these filters.</p>
                                        <button className="btn-secondary" onClick={openMatchListModal}>Open Matches</button>
                                        <button className="btn-secondary" onClick={openGenreModal}>Change Genre</button>
                                    </div>
                                ) : null
                            }
                        />
                    </div>

                    <div className="swipe-controls">
                        <button
                            className="jelly-button--compact nope-button"
                            onClick={() => deckRef.current?.commit("left")}
                            disabled={state.cardDeck.length === 0}
                        >
                            <span className="swipe-button-glyph" aria-hidden="true">✕</span>Nope
                        </button>
                        <button className="btn-secondary undo-button" onClick={undo}>Undo</button>
                        <button
                            className="jelly-button--compact like-button"
                            onClick={() => deckRef.current?.commit("right")}
                            disabled={state.cardDeck.length === 0}
                        >
                            <span className="swipe-button-glyph" aria-hidden="true">✓</span>Like
                        </button>
                    </div>
                    <p className="card-item-instructions">Tap for details · Arrow keys to swipe</p>
                </div>

                <div className="swipe-footer">
                    <button className="btn-destructive end-session" onClick={endSession}>End Session</button>
                    <button className="btn-secondary matches" onClick={openMatchListModal}>Matches</button>
                </div>

                {state.matchFound && <MatchFoundModal onClose={dismissMatch} matchItem={state.matchItem} />}
                {showGenreModal && <GenreModal onClose={closeGenreModal} />}
                {showMatchListModal && <MatchListModal onClose={closeMatchListModal} />}
            </>
        )
    } else {
        return (
            <>
                {errorBanner}
                <HostWaiting endSession={endSession} />
            </>
        )
    }

}
