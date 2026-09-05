import React from 'react'
import ActorElements from './ActorElements'
import PosterImage from './PosterImage'
import { formatRating } from './format'
import type { JSX } from "react"
import type { CardItem } from './types'

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
    setDragX: React.Dispatch<React.SetStateAction<number>>,
    /** 0 = the top card; 1, 2 = cards offset behind it (see SwipePage slicing). */
    stackIndex: number,
    zIndex: number
    onSwipe?: (
        cardItem: CardItem,
        direction: "left" | "right"
    ) => void
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

export default function CardItemView({ cardItem, setDragX, stackIndex, zIndex, onSwipe }: CardItemViewProps): JSX.Element {
    const isTopCard = stackIndex === 0
    const [position, setPosition] = React.useState<Position>(DEFAULT_POSITION)
    const [showDetails, setShowDetails] = React.useState<boolean>(false)
    const divRef = React.useRef<HTMLDivElement | null>(null)
    const [isDragging, setIsDragging] = React.useState<boolean>(false)
    const hasDragged = React.useRef<boolean>(false)
    const startX = React.useRef<number>(0)
    const currentX = React.useRef<number>(0)

    const { duration, mediaId, mediaType, rating, seasonCount = null, summary, posterUrl, title, year }: CardItem = cardItem
    const mediaText: string = mediaType === "movie" ? "Movie" : mediaType === "tv_show" ? "TV" : ""
    const seasonsText: string = seasonCount !== null && seasonCount === 1 ? ` • ${seasonCount} Season` : seasonCount !== null && seasonCount > 1 ? ` • ${seasonCount} Seasons` : ""


    const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
        setIsDragging(true)
        hasDragged.current = false
        startX.current = e.clientX

        e.currentTarget.setPointerCapture(e.pointerId)
    }

    const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
        if (!isDragging) return

        const deltaX: number = e.clientX - startX.current
        currentX.current = deltaX
        setDragX(deltaX)

        if (Math.abs(deltaX) > 5) {
            hasDragged.current = true
        }

        setPosition({
            x: deltaX,
            y: Math.abs(deltaX) / 10,
            rotation: deltaX / 10
        })
     }


    const handlePointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
        setIsDragging(false)
        e.currentTarget.releasePointerCapture(e.pointerId)
        setDragX(0)

        const swipeThreshold: number = 120

        if (Math.abs(currentX.current) > swipeThreshold) {
            const direction = currentX.current > 0 ? 1 : -1
            setPosition({
                x: direction * 1000,
                y: 0,
                rotation: currentX.current / 5
            })

            void onSwipe?.(
                cardItem,
                direction === 1 ? "right" : "left"
            )
        } else {
            setPosition(DEFAULT_POSITION)
        }
     }


    const toggleDetails = (e: React.MouseEvent<HTMLDivElement>) => {
        if (e.currentTarget.tagName === "BUTTON") return
        if (hasDragged.current) return
        setShowDetails(prev => !prev)
    }

    return (
        <div
            ref={divRef}
            className={`card-item-container ${showDetails ? "flipped" : ""} ${!isTopCard ? "stack-back" : ""}`}
            onClick={toggleDetails}
            onPointerDown={isTopCard ? handlePointerDown : undefined}
            onPointerMove={isTopCard ? handlePointerMove : undefined}
            onPointerUp={isTopCard ? handlePointerUp : undefined}
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
                        <button
                            onClick={(e: React.MouseEvent<HTMLButtonElement>) => e.stopPropagation()}
                            onPointerDown={(e: React.PointerEvent<HTMLButtonElement>) => e.stopPropagation()}
                            className="watch-trailer"
                        >
                            Watch Trailer
                        </button>
                    </div>
                    <p className="card-item-description">
                        {summary}
                    </p>

                    {showDetails && (
                        <ActorElements mediaId={mediaId} />
                    )}

                </div>
            </div>
        </div>
    )
}
