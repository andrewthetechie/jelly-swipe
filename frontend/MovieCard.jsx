import React from 'react'
import { actorElements } from "./assets/test-info"
import moanaPoster from "./assets/moana-poster.jpg"
import sadLogo from "./assets/sad.png"
import { apiUrl } from "./api"
const DEFAULT_POSITION = {
    x: 0,
    y: 0,
    rotation: 0
}

export default function MovieCard({ card, setDragX, isTopCard, zIndex }) {
    const [position, setPosition] = React.useState(DEFAULT_POSITION)
    const [showDetails, setShowDetails] = React.useState(false)
    const divRef = React.useRef(null)
    const isDragging = React.useRef(false)
    const hasDragged = React.useRef(false)
    const startX = React.useRef(0)
    const currentX = React.useRef(0)

    const { duration, media_id: mediaId, media_type: mediaType, rating, season_count, summary, thumb, title, year } = card
    const mediaText = mediaType === "movie" ? "Movie" : mediaType === "tv_show" ? "TV" : ""
    const seasonsText = season_count === 1 ? ` • ${season_count} Season` : season_count > 1 ? ` • ${season_count} Seasons` : ""
    

    const handlePointerDown = (e) => {
        isDragging.current = true
        hasDragged.current = false
        startX.current = e.clientX

        e.currentTarget.setPointerCapture(e.pointerId)
    }

    const handlePointerMove = (e) => {
        if (!isDragging.current) return

        const deltaX = e.clientX - startX.current
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

     const handlePointerUp = (e) => {
        isDragging.current = false
        e.currentTarget.releasePointerCapture(e.pointerId)
        setDragX(0)

        const swipeThreshold = 120

        if (Math.abs(currentX.current) > swipeThreshold) {
            const direction = currentX.current > 0 ? 1 : -1
            setPosition({
                x: direction * 1000,
                y: 0,
                rotation: currentX.current / 5
            })

            // remove card after animation, trigger next card, API call
        } else {
            setPosition(DEFAULT_POSITION)
        }
     }

    
    const toggleDetails = (e) => {
        if (e.target.tagName === "BUTTON") return
        if (hasDragged.current) return
        setShowDetails(prev => !prev)
    } 

    return (
        <div 
            ref={divRef}
            className={`movie-card-container ${showDetails ? "flipped" : ""}`} 
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
                    rotate(${position.rotation}deg)
                `,
                transition: isDragging.current ? "none" : "transform 0.4s ease"
            }}
        >
          <div className="movie-card-inner">
                <div className="movie-card front">
                    <div className="media-type">{mediaText}{seasonsText}</div>
                    <img src={thumb ? apiUrl(thumb).toString() : sadLogo} alt={title} className="movie-poster" draggable="false" />
                    {!thumb && <div className="no-poster">No poster available</div>}
                </div>

                <div className="movie-card back">
                    <h2 className="movie-title">{title}</h2>
                    <div className="movie-info">
                        {rating && <div className="movie-score">IMDb {rating != null ? rating.toFixed(2) : "N/A"}</div>}
                        {duration && <div className="movie-runtime">{duration}</div>}
                        {year && <div className="movie-year">{year}</div>}
                    </div>
                    <div className="trailer">
                        <button onClick={(e) => e.stopPropagation()} onPointerDown={(e) => e.stopPropagation()} className="watch-trailer">WATCH TRAILER</button>
                    </div>
                    <p className="movie-description">
                        {summary}
                    </p>
                    <div className="movie-cast">
                        {actorElements}
                    </div>
                </div>
            </div>
        </div>
    )
}