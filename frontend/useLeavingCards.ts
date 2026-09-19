import React from "react"
import type { CardItem } from "./types"

/**
 * A committed card kept mounted in SwipePage's "leaving slot" so its fly-off
 * exit animation can be seen (issue #360).
 */
export interface LeavingCard {
    card: CardItem
    direction: "left" | "right"
    /** Unique per commit (mediaId + monotonically increasing seq), so React
     * remounts each leaving card fresh at rest and undo + re-swipe of the same
     * card never collides. */
    key: string
}

interface UseLeavingCardsReturn {
    /** The leaving entries currently animating out, in commit order. */
    leavingCards: LeavingCard[]
    /** Record a committed card's leaving entry and schedule its removal. */
    commit: (card: CardItem, direction: "left" | "right") => void
}

/**
 * The reduced-motion hold duration for a leaving card, read once via
 * `window.matchMedia` — the same determination CardItemView uses to derive the
 * exit transition duration, so the animation and the unmount hold stay in lock
 * step (400ms normally, 150ms under `prefers-reduced-motion: reduce`).
 */
function leavingHoldMs(): number {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 150 : 400
}

/**
 * State for SwipePage's "leaving card" overlay (issue #360): the deck slices
 * the moment a swipe succeeds, so the committed card would unmount mid-exit;
 * this hook records it as a non-interactive leaving entry that self-removes
 * after the exit transition duration. It is deliberately NOT a reducer change —
 * `roomSession.ts` / `RoomSessionProvider.tsx` keep slicing the deck and
 * updating `swipeHistory` exactly as before, so undo keeps working immediately.
 */
export const useLeavingCards = (deck: CardItem[]): UseLeavingCardsReturn => {
    const [leavingCards, setLeavingCards] = React.useState<LeavingCard[]>([])
    // Per-entry timers, keyed by the entry key, so rapid consecutive swipes
    // each get their own removal timer and entries never accumulate.
    const timersRef = React.useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map())
    const seqRef = React.useRef<number>(0)
    const leavingCardsRef = React.useRef(leavingCards)

    React.useEffect(() => {
        leavingCardsRef.current = leavingCards
    }, [leavingCards])

    const removeEntry = React.useCallback((key: string) => {
        const timer = timersRef.current.get(key)
        if (timer !== undefined) {
            clearTimeout(timer)
            timersRef.current.delete(key)
        }
        setLeavingCards((prev) => prev.filter((entry) => entry.key !== key))
    }, [])

    const commit = React.useCallback((card: CardItem, direction: "left" | "right") => {
        seqRef.current += 1
        const key = `leaving-${card.mediaId}-${seqRef.current}`
        const entry: LeavingCard = { card, direction, key }
        setLeavingCards((prev) => [...prev, entry])
        const timer = setTimeout(() => removeEntry(key), leavingHoldMs())
        timersRef.current.set(key, timer)
    }, [removeEntry])

    // Undo interplay (issue #360): when an undo restores a card that is still
    // mid-exit (the deck head's mediaId equals a leaving entry's), drop that
    // leaving entry so no ghost duplicate keeps flying over the restored card.
    React.useEffect(() => {
        const head = deck[0]
        if (!head) return
        for (const entry of leavingCardsRef.current) {
            if (entry.card.mediaId === head.mediaId) {
                removeEntry(entry.key)
            }
        }
    }, [deck, removeEntry])

    // Clear every entry's timer on unmount so no timer outlives the hook. The
    // Map reference never changes (entries are added/removed in place), so
    // capturing it here is safe.
    React.useEffect(() => {
        const timers = timersRef.current
        return () => {
            timers.forEach((timer) => clearTimeout(timer))
            timers.clear()
        }
    }, [])

    return {
        leavingCards,
        commit,
    }
}
