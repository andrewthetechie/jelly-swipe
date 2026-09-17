import React from 'react'
import ActorElements from './ActorElements'
import PosterImage from './PosterImage'
import { formatRating } from './format'
import {
    computeVelocity,
    exitDistanceFor,
    shouldCommitSwipe,
    stampSignal,
    swipeThresholdFor,
    trackSample,
} from './swipeGesture'
import type { PointerSample } from './swipeGesture'
import type { JSX } from "react"
import type { CardItem } from './types'
import { fetchTrailer, RoomApiError } from './roomApi'

type Position = {
    x: number,
    y: number,
    rotation: number
}

const DEFAULT_POSITION: Position = {
    x: 0,
    y: 0,
    rotation: 0
}

interface CardItemViewProps {
    cardItem: CardItem,
    /** 0 = the top card; 1, 2 = cards offset behind it (see SwipePage slicing). */
    stackIndex: number,
    zIndex: number
    onSwipe?: (
        cardItem: CardItem,
        direction: "left" | "right"
    ) => void | Promise<void>
}

// Stack depth styling (see issue #343). Depth `i` is how many cards this one
// sits behind (i === 0 is the top card).
//
// Back cards are scaled down *and* pushed up past the top card's edge. The
// push is what makes the stack visible at all: transform-origin is the centre,
// so scaling by `s` already insets every edge by height * (1 - s) / 2, and a
// card that only shrinks disappears entirely inside the top card's opaque
// rectangle. The sliver that shows above the top card is therefore
//   height * (STACK_STEP_Y_PCT / 100 - STACK_STEP_SCALE / 2) * i ≈ 14px per step,
// and `.swipe-deck` reserves `--deck-stack-reserve` at the top of the deck so
// the stack sits inside the deck's footprint instead of over the header.
//
// translateY is a percentage (of the card's own height) rather than pixels so
// the sliver stays proportional across the deck's three breakpoint heights.
const STACK_STEP_Y_PCT = 4.75
const STACK_STEP_SCALE = 0.05
const STACK_STEP_BRIGHTNESS = 0.15

function stackTransform(i: number): string {
    if (i === 0) return ""
    return `translateY(${-i * STACK_STEP_Y_PCT}%) scale(${1 - i * STACK_STEP_SCALE})`
}

function stackBrightness(i: number): string | undefined {
    // Only back cards get a filter, so the top card keeps its exact rendering
    // path (no filter-created containing block around the 3D flip).
    if (i === 0) return undefined
    return `brightness(${1 - i * STACK_STEP_BRIGHTNESS})`
}

export type CardItemViewHandle = {
    commitSwipe: (direction: "left" | "right") => Promise<void>
    toggleDetails: () => void
}

function CardItemViewInner(
    { cardItem, stackIndex, zIndex, onSwipe }: CardItemViewProps,
    ref: React.ForwardedRef<CardItemViewHandle>,
): JSX.Element {
    const isTopCard = stackIndex === 0
    const [position, setPosition] = React.useState<Position>(DEFAULT_POSITION)
    const [showDetails, setShowDetails] = React.useState<boolean>(false)
    const divRef = React.useRef<HTMLDivElement | null>(null)
    const [isDragging, setIsDragging] = React.useState<boolean>(false)
    const hasDragged = React.useRef<boolean>(false)
    const startX = React.useRef<number>(0)
    const currentX = React.useRef<number>(0)
    const samples = React.useRef<PointerSample[]>([])
    // Mirrors `isDragging` but readable synchronously inside the same handler —
    // needed because `lostpointercapture` fires from our own releasePointerCapture()
    // on a normal release and must not undo a commit (see handleLostPointerCapture).
    const dragActive = React.useRef<boolean>(false)
    // Set by the single commit path; a second button press, a late pointer event,
    // or a re-drag on the still-mounted card must not double-fire onSwipe.
    const committed = React.useRef<boolean>(false)
    const thresholdPx = React.useRef<number>(swipeThresholdFor(0))
    const [signal, setSignal] = React.useState<number>(0)

    // Trailer state machine: idle → loading → (playing | unavailable).
    const [trailerState, setTrailerState] = React.useState<"idle" | "loading" | "playing" | "unavailable">("idle")
    const [trailerKey, setTrailerKey] = React.useState<string | null>(null)
    const trailerAbort = React.useRef<AbortController | null>(null)

    // Abort any in-flight trailer fetch when the card unmounts (issue #339),
    // matching the pattern in useMovieCast.tsx:31.
    React.useEffect(() => {
        return () => {
            trailerAbort.current?.abort()
        }
    }, [])

    const loadTrailer = () => {
        if (trailerState !== "idle") return
        setTrailerState("loading")
        trailerAbort.current = new AbortController()
        fetchTrailer(mediaId, trailerAbort.current.signal)
            .then((data) => {
                setTrailerKey(data.youtube_key)
                setTrailerState("playing")
            })
            .catch((err) => {
                // Unmounting aborts the request; ignore that as a no-op rather
                // than flipping to "unavailable" on a component that is gone.
                if ((err as Error).name === "AbortError") return
                // A 404 is the expected "no trailer" answer, not an error.
                if (err instanceof RoomApiError && err.status === 404) {
                    setTrailerState("unavailable")
                    return
                }
                console.error("Error fetching trailer:", err)
                setTrailerState("unavailable")
            })
    }

    const likeStrength: number = Math.max(signal, 0)
    const nopeStrength: number = Math.max(-signal, 0)

    const { duration, mediaId, mediaType, rating, seasonCount = null, summary, posterUrl, title, year }: CardItem = cardItem
    const mediaText: string = mediaType === "movie" ? "Movie" : mediaType === "tv_show" ? "TV" : ""
    const seasonsText: string = seasonCount !== null && seasonCount === 1 ? ` • ${seasonCount} Season` : seasonCount !== null && seasonCount > 1 ? ` • ${seasonCount} Seasons` : ""


    // The single exit path for any drag that does NOT commit: snap-back,
    // OS/browser cancellation, and capture loss (issue #342).
    const resetDrag = () => {
        dragActive.current = false
        currentX.current = 0
        samples.current = []
        setIsDragging(false)
        setSignal(0)
        setPosition(DEFAULT_POSITION)
    }

    // The single exit path for a committed swipe. Both the drag gesture
    // (handlePointerUp) and the imperative handle (commitSwipe on the ref)
    // funnel through here so the exit animation and onSwipe call cannot drift
    // apart. Guards: only the top card can commit, and only when no drag is live
    // and the card has not already committed.
    const commitSwipe = async (direction: 1 | -1, velocity: number, dragDistance: number): Promise<void> => {
        if (stackIndex !== 0) return
        if (dragActive.current) return
        if (committed.current) return
        committed.current = true

        // Hold the stamp lit through the exit — the card has committed.
        setSignal(direction)
        setPosition({
            x: direction * exitDistanceFor(
                velocity,
                divRef.current?.offsetWidth ?? 0,
                window.innerWidth,
            ),
            y: 0,
            // The drag path rotates by dragDistance / 5 of the live travel; an
            // imperative button/key commit has no drag distance, so use a small
            // direction-signed constant.
            rotation: dragDistance !== 0 ? dragDistance / 5 : direction * 12,
        })

        const result = onSwipe?.(
            cardItem,
            direction === 1 ? "right" : "left"
        )
        if (result) {
            try {
                await result
            } catch {
                // The swipe failed to save (e.g. a network error). Snap the card
                // back to its resting transform and clear the committed guard so
                // it can be re-swiped — the error banner promises a retry.
                committed.current = false
                setSignal(0)
                setPosition(DEFAULT_POSITION)
            }
        }
    }

    const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
        setIsDragging(true)
        dragActive.current = true
        hasDragged.current = false
        startX.current = e.clientX
        currentX.current = 0
        samples.current = [{ x: e.clientX, time: e.timeStamp }]
        // Measured once per gesture rather than per move, to avoid layout thrash.
        thresholdPx.current = swipeThresholdFor(divRef.current?.offsetWidth ?? 0)

        e.currentTarget.setPointerCapture(e.pointerId)
    }

    const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
        if (!isDragging) return

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
            rotation: deltaX / 10
        })
    }

    const handlePointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
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
            commitSwipe(direction, velocity, distance)
        } else {
            resetDrag()
        }
    }

    // The OS or browser took the pointer away mid-drag — incoming call, notification,
    // iOS back-swipe, context menu. `pointerup` never arrives (issue #342).
    // Guarded like handleLostPointerCapture: a cancel arriving after a commit
    // (e.g. a second finger lifting) must not snap the committed card back to
    // rest on-screen, since `onSwipe` has already fired and been seen.
    const handlePointerCancel = () => {
        if (!dragActive.current) return
        resetDrag()
    }

    // Also fires from our own releasePointerCapture() on a normal release, so it must
    // only act while a drag is genuinely still live.
    const handleLostPointerCapture = () => {
        if (!dragActive.current) return
        resetDrag()
    }


    const handleDetailsClick = (e: React.MouseEvent<HTMLDivElement>) => {
        if (e.currentTarget.tagName === "BUTTON") return
        if (hasDragged.current) return
        setShowDetails(prev => !prev)
    }

    // Imperative flip for the ref handle — same top-card guard as commitSwipe.
    // Deliberately does NOT reuse handleDetailsClick: its BUTTON/hasDragged
    // guards are about real click events and don't apply to a programmatic call.
    const toggleDetails = () => {
        if (stackIndex !== 0) return
        setShowDetails(prev => !prev)
    }

    React.useImperativeHandle(ref, () => ({
        commitSwipe: (direction: "left" | "right") =>
            commitSwipe(direction === "right" ? 1 : -1, 0, 0),
        toggleDetails,
    }))

    return (
        <div
            ref={divRef}
            className={`card-item-container ${showDetails ? "flipped" : ""} ${!isTopCard ? "stack-back" : ""}`}
            onClick={handleDetailsClick}
            onPointerDown={isTopCard ? handlePointerDown : undefined}
            onPointerMove={isTopCard ? handlePointerMove : undefined}
            onPointerUp={isTopCard ? handlePointerUp : undefined}
            onPointerCancel={isTopCard ? handlePointerCancel : undefined}
            onLostPointerCapture={isTopCard ? handleLostPointerCapture : undefined}
            style={{
                zIndex,
                pointerEvents: isTopCard ? "auto" : "none",
                cursor: "grab",
                userSelect: "none",
                touchAction: "none",
                transform: `
                    translate(${position.x}px, ${position.y}px)
                    rotate(${position.rotation}deg) ${stackTransform(stackIndex)}
                `,
                filter: stackBrightness(stackIndex),
                transition: isDragging ? "none" : "transform 0.4s ease, filter 0.4s ease"
            }}
        >
          <div className="card-item-inner">
                <div className="card-item front">
                    <div className="media-type">{mediaText}{seasonsText}</div>
                    <PosterImage posterUrl={posterUrl} alt={title} className="card-item-poster" draggable={false} showNoPosterLabel />
                </div>

                <div className="card-item back">
                    <h2 className="card-item-title">{title}</h2>
                    <div className="card-item-info">
                        {rating != null && <div className="card-item-score">IMDb {formatRating(rating)}</div>}
                        {duration && <div className="card-item-runtime">{duration}</div>}
                        {year && <div className="card-item-year">{year}</div>}
                    </div>
                    <div className="trailer">
                        {trailerState === "idle" && (
                            <button
                                onClick={(e: React.MouseEvent<HTMLButtonElement>) => {
                                    e.stopPropagation()
                                    loadTrailer()
                                }}
                                onPointerDown={(e: React.PointerEvent<HTMLButtonElement>) => e.stopPropagation()}
                                className="btn-secondary watch-trailer"
                            >
                                Watch trailer
                            </button>
                        )}
                        {trailerState === "loading" && (
                            <button
                                disabled
                                onClick={(e: React.MouseEvent<HTMLButtonElement>) => e.stopPropagation()}
                                onPointerDown={(e: React.PointerEvent<HTMLButtonElement>) => e.stopPropagation()}
                                className="btn-secondary watch-trailer"
                            >
                                Loading trailer…
                            </button>
                        )}
                        {trailerState === "playing" && trailerKey && showDetails && (
                            <div
                                onClick={(e: React.MouseEvent<HTMLDivElement>) => e.stopPropagation()}
                                onPointerDown={(e: React.PointerEvent<HTMLDivElement>) => e.stopPropagation()}
                            >
                                <iframe
                                    src={`https://www.youtube.com/embed/${trailerKey}?autoplay=1`}
                                    title={`${title} trailer`}
                                    allow="autoplay; encrypted-media; picture-in-picture"
                                    allowFullScreen
                                    loading="lazy"
                                />
                            </div>
                        )}
                        {trailerState === "unavailable" && (
                            <p className="trailer-unavailable">No trailer available</p>
                        )}
                    </div>
                    <p className="card-item-description">
                        {summary}
                    </p>

                    {showDetails && (
                        <ActorElements mediaId={mediaId} />
                    )}

                </div>
            </div>
            {isTopCard && (
                <>
                    <div className="swipe-rim swipe-rim-like" style={{ opacity: likeStrength }} aria-hidden="true" />
                    <div className="swipe-rim swipe-rim-nope" style={{ opacity: nopeStrength }} aria-hidden="true" />
                    <div
                        className="swipe-stamp swipe-stamp-like"
                        /* `scale` must be a String, not a number: React 18 does not
                           list `scale` as a unitless property, so a number would
                           serialise as "0.86px" and silently do nothing. */
                        style={{ opacity: likeStrength, scale: String(0.86 + 0.14 * likeStrength) }}
                        aria-hidden="true"
                    >
                        <span className="swipe-stamp-glyph">✓</span>Like
                    </div>
                    <div
                        className="swipe-stamp swipe-stamp-nope"
                        style={{ opacity: nopeStrength, scale: String(0.86 + 0.14 * nopeStrength) }}
                        aria-hidden="true"
                    >
                        <span className="swipe-stamp-glyph">✕</span>Nope
                    </div>
                </>
            )}
        </div>
    )
}

const CardItemView = React.forwardRef<CardItemViewHandle, CardItemViewProps>(CardItemViewInner)
export default CardItemView
