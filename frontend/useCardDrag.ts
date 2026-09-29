// useCardDrag.ts — the card's pointer-drag gesture controller (issue #406,
// first slice). Owns the drag state machine that used to live inside
// CardItemView's `CardItemViewInner`: the drag-active / committed / has-dragged
// guards, per-gesture threshold measurement, sample accumulation, the stamp
// signal, and the snap-back / cancel / lost-pointer-capture exits.
//
// It is deliberately JSX-free and reuses — does not copy — the pure maths in
// ./swipeGesture (`swipeThresholdFor`, `trackSample`, `computeVelocity`,
// `stampSignal`, `shouldCommitSwipe`). It does NOT import `flyOffTarget` or
// `parseComputedTransform`: those belong to the component's commit funnel and
// exit capture (issues #360, #399) and stay with the component.

import React from "react"
import {
    computeVelocity,
    shouldCommitSwipe,
    stampSignal,
    swipeThresholdFor,
    trackSample,
} from "./swipeGesture"
import type { PointerSample, Position } from "./swipeGesture"

const DEFAULT_POSITION: Position = {
    x: 0,
    y: 0,
    rotation: 0,
}

/** A commit verdict handed to the component's commit funnel on a release that
 * passes the swipe threshold. The hook never calls `onSwipe` itself and never
 * computes a fly-off target — that stays with the component (issues #360, #399). */
export type CommitVerdict = (
    direction: 1 | -1,
    velocity: number,
    dragDistance: number,
) => void

export interface UseCardDragReturn {
    /** The card's live drag transform (x / y / rotation). */
    position: Position
    /** Signed stamp strength in [-1, 1] (see swipeGesture.stampSignal). */
    signal: number
    /** Render state, not a ref: the card's inline transition switches on it. */
    isDragging: boolean
    /** True once the current gesture travelled > 5px; guards the details-flip
     * click. Resets at the start of each new gesture. */
    hasDragged: () => boolean
    /** Test-and-set arm for the committed guard — the sole mutator of
     * `committed`. Returns false when a drag is live or the card is already
     * armed, true when this call armed it. */
    armCommit: () => boolean
    /** Clear the committed guard so an onSwipe rejection can re-arm the card. */
    releaseCommitted: () => void
    /** Synchronous consult of the live-drag guard (the commit funnel refuses a
     * commit while this is true). */
    isDragActive: () => boolean
    /** Commit-path presentation: set the stamp signal (the committed direction). */
    setCommitSignal: (value: number) => void
    /** Commit-path presentation: set the card transform (fly-off / snap-back). */
    setCommitPosition: (value: Position) => void
    handlePointerDown: (e: React.PointerEvent<HTMLDivElement>) => void
    handlePointerMove: (e: React.PointerEvent<HTMLDivElement>) => void
    handlePointerUp: (e: React.PointerEvent<HTMLDivElement>) => void
    handlePointerCancel: () => void
    handleLostPointerCapture: () => void
}

/**
 * The card drag gesture controller (issue #406). Called unconditionally with an
 * `enabled` flag mirroring `!isExit && isTopCard` so the rules of hooks are
 * never violated — when `enabled` is false the returned handlers are inert and
 * no gesture state changes. `elementRef` is the card's divRef, shared with the
 * exit-capture path; its width is measured once per gesture at pointerdown.
 */
export const useCardDrag = (
    enabled: boolean,
    elementRef: React.RefObject<HTMLDivElement | null>,
    onCommitVerdict?: CommitVerdict,
): UseCardDragReturn => {
    const [position, setPosition] = React.useState<Position>(DEFAULT_POSITION)
    const [isDragging, setIsDragging] = React.useState<boolean>(false)
    const hasDragged = React.useRef<boolean>(false)
    const startX = React.useRef<number>(0)
    const currentX = React.useRef<number>(0)
    const samples = React.useRef<PointerSample[]>([])
    // Mirrors `isDragging` but readable synchronously inside the same handler —
    // needed because `lostpointercapture` fires from our own releasePointerCapture()
    // on a normal release and must not undo a commit (see handleLostPointerCapture).
    const dragActive = React.useRef<boolean>(false)
    // Set by the single commit path (armCommit); a second button press, a late
    // pointer event, or a re-drag on the still-mounted card must not double-fire.
    const committed = React.useRef<boolean>(false)
    const thresholdPx = React.useRef<number>(swipeThresholdFor(0))
    const [signal, setSignal] = React.useState<number>(0)

    // The single exit path for any drag that does NOT commit: snap-back,
    // OS/browser cancellation, and capture loss (issue #342).
    const resetDrag = React.useCallback(() => {
        dragActive.current = false
        currentX.current = 0
        samples.current = []
        setIsDragging(false)
        setSignal(0)
        setPosition(DEFAULT_POSITION)
    }, [])

    const handlePointerDown = React.useCallback((e: React.PointerEvent<HTMLDivElement>) => {
        if (!enabled) return
        setIsDragging(true)
        dragActive.current = true
        hasDragged.current = false
        startX.current = e.clientX
        currentX.current = 0
        samples.current = [{ x: e.clientX, time: e.timeStamp }]
        // Measured once per gesture rather than per move, to avoid layout thrash.
        thresholdPx.current = swipeThresholdFor(elementRef.current?.offsetWidth ?? 0)

        e.currentTarget.setPointerCapture(e.pointerId)
    }, [elementRef, enabled])

    const handlePointerMove = React.useCallback((e: React.PointerEvent<HTMLDivElement>) => {
        if (!enabled) return
        if (!dragActive.current) return

        const deltaX: number = e.clientX - startX.current
        currentX.current = deltaX
        samples.current = trackSample(samples.current, { x: e.clientX, time: e.timeStamp })

        if (Math.abs(deltaX) > 5) {
            hasDragged.current = true
        }

        setSignal(stampSignal(deltaX, computeVelocity(samples.current), thresholdPx.current))
        setPosition({
            x: deltaX,
            y: Math.abs(deltaX) / 10,
            rotation: deltaX / 10,
        })
    }, [enabled])

    const handlePointerUp = React.useCallback((e: React.PointerEvent<HTMLDivElement>) => {
        if (!enabled) return
        if (!dragActive.current) return
        // Cleared BEFORE releasePointerCapture, which synthesises a
        // `lostpointercapture` that would otherwise reset a committed card.
        dragActive.current = false
        setIsDragging(false)
        e.currentTarget.releasePointerCapture(e.pointerId)

        const distance: number = currentX.current
        const velocity: number = computeVelocity(samples.current)
        samples.current = []

        if (shouldCommitSwipe(distance, velocity, thresholdPx.current)) {
            const direction: 1 | -1 = distance > 0 ? 1 : -1
            onCommitVerdict?.(direction, velocity, distance)
        } else {
            resetDrag()
        }
    }, [enabled, onCommitVerdict, resetDrag])

    // The OS or browser took the pointer away mid-drag — incoming call,
    // notification, iOS back-swipe, context menu. `pointerup` never arrives
    // (issue #342). Guarded like handleLostPointerCapture: a cancel arriving
    // after a commit (e.g. a second finger lifting) must not snap the committed
    // card back to rest on-screen, since the verdict has already been handed off.
    const handlePointerCancel = React.useCallback(() => {
        if (!enabled) return
        if (!dragActive.current) return
        resetDrag()
    }, [enabled, resetDrag])

    // Also fires from our own releasePointerCapture() on a normal release, so it
    // must only act while a drag is genuinely still live.
    const handleLostPointerCapture = React.useCallback(() => {
        if (!enabled) return
        if (!dragActive.current) return
        resetDrag()
    }, [enabled, resetDrag])

    // Test-and-set arm for the committed guard — the sole mutator of `committed`.
    // Refuses while a drag is live or the card is already armed, mirroring the
    // commit funnel's guard order (dragActive, then committed).
    const armCommit = React.useCallback(() => {
        if (dragActive.current) return false
        if (committed.current) return false
        committed.current = true
        return true
    }, [])

    // Clear the committed guard so an onSwipe rejection can re-arm the card.
    const releaseCommitted = React.useCallback(() => {
        committed.current = false
    }, [])

    const isDragActive = React.useCallback(() => dragActive.current, [])

    const hasDraggedFn = React.useCallback(() => hasDragged.current, [])

    // Commit-path presentation setters: the component's commit funnel lights the
    // stamp and sets the fly-off / snap-back transform through the hook, since
    // signal/position now live here.
    const setCommitSignal = React.useCallback((value: number) => {
        setSignal(value)
    }, [])

    const setCommitPosition = React.useCallback((value: Position) => {
        setPosition(value)
    }, [])

    return {
        position,
        signal,
        isDragging,
        hasDragged: hasDraggedFn,
        armCommit,
        releaseCommitted,
        isDragActive,
        setCommitSignal,
        setCommitPosition,
        handlePointerDown,
        handlePointerMove,
        handlePointerUp,
        handlePointerCancel,
        handleLostPointerCapture,
    }
}
