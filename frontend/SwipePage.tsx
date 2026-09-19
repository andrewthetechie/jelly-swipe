import React from "react"
import HostWaiting from "./HostWaiting"
import CardItemView, { type CardItemViewHandle, type Position } from "./CardItemView"
import MatchFoundModal from "./MatchFoundModal"
import GenreModal from "./GenreModal"
import MatchListModal from "./MatchListModal"
import { useRoomStateContext } from "./RoomContextProvider"
import type { JSX } from "react"
import type { CardItem } from './types'
import { useRoomSession } from "./RoomSessionProvider"
import { useLeavingCards } from "./useLeavingCards"

// Leaving cards render above every stack card (stack cards get zIndex = index,
// i.e. ≤ 2), so a committed card visibly flies off over the promoted stack.
const LEAVING_CARD_Z_INDEX = 10

export default function SwipePage(): JSX.Element {
    const { state, swipe, undo, toggleHideWatched, dismissMatch, endSession, clearError, retryDeckFetch } = useRoomSession()
    const [showMatchListModal, setShowMatchListModal] = React.useState<boolean>(false)
    const [showGenreModal, setShowGenreModal] = React.useState<boolean>(false)
    const { isSoloMode } = useRoomStateContext()
    const { leavingCards, commit } = useLeavingCards(state.cardDeck)

    // Render at most 3 cards (the top card + ≤2 back cards). Deeper cards are
    // dropped entirely (issue #343) — undo still works because undo re-adds the
    // card to `cardDeck` state and it mounts fresh at the top (see roomSession).
    const visibleCards = state.cardDeck.slice(0, 3).reverse()

    // Imperative handle to the top card, so the Nope/Like buttons reuse the
    // exact commit path a drag uses (same exit transform, same onSwipe call).
    // Only the top card gets the ref (see the map below).
    const cardRef = React.useRef<CardItemViewHandle | null>(null)
    const commitSwipe = React.useCallback((direction: "left" | "right") => {
        cardRef.current?.commitSwipe(direction)
    }, [])

    // Wrap the provider's `swipe` so a successful commit also records a
    // leaving entry. Only after `await swipe(...)` succeeds (so SWIPE_SUCCEEDED
    // and the leaving entry land in one React batch) is the entry recorded,
    // carrying the committed card's transform so the leaving card continues
    // the exit instead of restarting at rest. On POST rejection, `swipe`
    // re-throws and this wrapper adds nothing and re-throws, so
    // CardItemView.commitSwipe's catch still snaps the card back and leaves it
    // retryable.
    const onSwipe = React.useCallback(async (card: CardItem, direction: "left" | "right", from: Position) => {
        await swipe(card, direction)
        commit(card, direction, from)
    }, [swipe, commit])

    // Keyboard swipe support (issue #344): Left/Right swipe, Up/Enter flip.
    // Inert while any modal is open or an interactive element has focus (so
    // Enter always activates a focused button), and ignores key-repeat so a
    // held key cannot machine-gun swipes.
    React.useEffect(() => {
        if (!state.roomReady) return
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.repeat) return
            if (state.matchFound || showGenreModal || showMatchListModal) return

            const active = document.activeElement
            if (active instanceof HTMLElement) {
                const tag = active.tagName
                if (
                    tag === "BUTTON" ||
                    tag === "INPUT" ||
                    tag === "TEXTAREA" ||
                    tag === "SELECT" ||
                    active.isContentEditable
                ) {
                    return
                }
            }

            switch (e.key) {
                case "ArrowLeft":
                    e.preventDefault()
                    commitSwipe("left")
                    break
                case "ArrowRight":
                    e.preventDefault()
                    commitSwipe("right")
                    break
                case "ArrowUp":
                case "Enter":
                    e.preventDefault()
                    cardRef.current?.toggleDetails()
                    break
            }
        }
        window.addEventListener("keydown", handleKeyDown)
        return () => window.removeEventListener("keydown", handleKeyDown)
    }, [state.roomReady, state.matchFound, showGenreModal, showMatchListModal, commitSwipe])

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
                        {state.deckError && state.cardDeck.length === 0 ? (
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
                        ) : (
                            visibleCards.map((cardItem: CardItem, index: number) => (
                                <CardItemView
                                    key={cardItem.mediaId}
                                    ref={visibleCards.length - 1 - index === 0 ? cardRef : undefined}
                                    cardItem={cardItem}
                                    // rendered order is reversed: the last card is the top.
                                    stackIndex={visibleCards.length - 1 - index}
                                    zIndex={index}
                                    onSwipe={onSwipe}
                                />
                            ))
                        )}
                        {leavingCards.map((entry) => (
                            <CardItemView
                                key={entry.key}
                                cardItem={entry.card}
                                stackIndex={0}
                                zIndex={LEAVING_CARD_Z_INDEX}
                                exitDirection={entry.direction}
                                exitFrom={entry.from}
                            />
                        ))}
                    </div>

                    <div className="swipe-controls">
                        <button
                            className="jelly-button--compact nope-button"
                            onClick={() => commitSwipe("left")}
                            disabled={state.cardDeck.length === 0}
                        >
                            <span className="swipe-button-glyph" aria-hidden="true">✕</span>Nope
                        </button>
                        <button className="btn-secondary undo-button" onClick={undo}>Undo</button>
                        <button
                            className="jelly-button--compact like-button"
                            onClick={() => commitSwipe("right")}
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
