import React from "react"
import CardItemView, { type CardItemViewHandle } from "./CardItemView"
import { EXIT_TRANSITION_MS, REDUCED_MOTION_EXIT_TRANSITION_MS, type Position } from "./swipeGesture"
import { useLeavingCards } from "./useLeavingCards"
import type { JSX } from "react"
import type { CardItem } from "./types"

// Leaving cards render above every stack card (stack cards get zIndex = index,
// i.e. ≤ 2), so a committed card visibly flies off over the promoted stack.
const LEAVING_CARD_Z_INDEX = 10

/**
 * Imperative surface for SwipePage's Nope/Like buttons and keyboard handler.
 * The deck module owns the whole commit choreography behind it: save-then-exit,
 * live-transform capture, leaving-entry lifetime, and stack ordering.
 */
export type SwipeDeckHandle = {
    commit: (direction: "left" | "right") => void
    toggleDetails: () => void
}

interface SwipeDeckProps {
    deck: CardItem[]
    /** Persist a committed card. SwipePage passes the session `swipe`; the deck
     * module awaits it and re-throws on rejection so CardItemView.commitSwipe's
     * catch still snaps the card back and leaves it retryable. */
    onSave: (card: CardItem, direction: "left" | "right") => void | Promise<void>
    /** The deck-error / deck-end empty-state node, rendered in place of the stack
     * when `deck` is empty. The deck module stays mounted across the empty state
     * so a just-committed leaving card keeps flying over it (issue #360): the
     * leaving entries are always rendered after this node, preserving the
     * original DOM order (empty-state div followed by leaving `.card-item-container`s). */
    emptyState?: JSX.Element | null
}

function SwipeDeckInner(
    { deck, onSave, emptyState }: SwipeDeckProps,
    ref: React.ForwardedRef<SwipeDeckHandle>,
): JSX.Element {
    // The single reduced-motion read on the commit path (issue #399). The exit
    // transition duration, the resting/snap-back transition, and the leaving-card
    // unmount hold are all derived here from the shared exit-duration constants
    // (swipeGesture.ts), so the animation and the hold can never drift apart.
    // The hold (ms) equals the animation, satisfying parent decision 5 (hold ≥
    // animation); `restTransitionSeconds` is seconds because CardItemView uses
    // it inline in a `transform Ns ease` string.
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    const restTransitionSeconds = (reducedMotion
        ? REDUCED_MOTION_EXIT_TRANSITION_MS
        : EXIT_TRANSITION_MS) / 1000
    const leavingHoldMs = reducedMotion
        ? REDUCED_MOTION_EXIT_TRANSITION_MS
        : EXIT_TRANSITION_MS

    const { leavingCards, commit } = useLeavingCards(deck, leavingHoldMs)

    // Render at most 3 cards (the top card + ≤2 back cards). Deeper cards are
    // dropped entirely (issue #343) — undo still works because undo re-adds the
    // card to `cardDeck` state and it mounts fresh at the top (see roomSession).
    const visibleCards = deck.slice(0, 3).reverse()

    // Imperative handle to the top card, so the Nope/Like buttons reuse the
    // exact commit path a drag uses (same exit transform, same onSwipe call).
    // Only the top card gets the ref (see the map below).
    const cardRef = React.useRef<CardItemViewHandle | null>(null)
    const commitSwipe = React.useCallback((direction: "left" | "right") => {
        cardRef.current?.commitSwipe(direction)
    }, [])

    // Wrap the session's `swipe` so a successful commit also records a leaving
    // entry. Only after `await onSave(...)` succeeds (so SWIPE_SUCCEEDED and the
    // leaving entry land in one React batch) is the entry recorded, carrying the
    // committed card's transform so the leaving card continues the exit instead
    // of restarting at rest. On POST rejection, `onSave` re-throws and this
    // wrapper adds nothing and re-throws, so CardItemView.commitSwipe's catch
    // still snaps the card back and leaves it retryable.
    //
    // When the POST resolves before the 0.4s commit transition finishes (the
    // common fast-LAN case), the committed card is still mounted and mid-flight.
    // Seed the leaving entry from its *live* transform (`captureExitTransform`,
    // read through the still-mounted top card's handle) rather than the commit
    // transition's final target, so the exit continues in one motion instead of
    // teleporting to the target the moment the swipe saves (issue #360). Falls
    // back to the threaded commit transform if the handle is unavailable.
    const onSwipe = React.useCallback(async (card: CardItem, direction: "left" | "right", from: Position) => {
        await onSave(card, direction)
        const liveFrom = cardRef.current?.captureExitTransform() ?? from
        commit(card, direction, liveFrom)
    }, [onSave, commit])

    React.useImperativeHandle(ref, () => ({
        commit: commitSwipe,
        toggleDetails: () => cardRef.current?.toggleDetails(),
    }))

    return (
        <>
            {deck.length === 0 ? (
                emptyState ?? null
            ) : (
                visibleCards.map((cardItem: CardItem, index: number) => (
                    <CardItemView
                        key={cardItem.mediaId}
                        ref={visibleCards.length - 1 - index === 0 ? cardRef : undefined}
                        cardItem={cardItem}
                        // rendered order is reversed: the last card is the top.
                        stackIndex={visibleCards.length - 1 - index}
                        zIndex={index}
                        restTransitionSeconds={restTransitionSeconds}
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
                    restTransitionSeconds={restTransitionSeconds}
                    exitDirection={entry.direction}
                    exitFrom={entry.from}
                />
            ))}
        </>
    )
}

const SwipeDeck = React.forwardRef<SwipeDeckHandle, SwipeDeckProps>(SwipeDeckInner)

export default SwipeDeck
