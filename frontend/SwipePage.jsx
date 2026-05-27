import React from "react"
import MovieCard from "./MovieCard"
import { RoomContext } from "./App"
import { apiFetch } from "./api"

export default function SwipePage( {cardDeck} ) {
    const [dragX, setDragX] = React.useState(0)
    const { currentRoomCode, setCurrentRoomCode } = React.useContext(RoomContext)

    const rightOpacity = 
        dragX > 20
            ? Math.min(Math.abs(dragX) / 200, 1)
            : 0
    const leftOpacity = 
        dragX < -20
            ? Math.min(Math.abs(dragX) / 200, 1)
            : 0
    const visibleCards = cardDeck.slice(0, 5).reverse()

    async function handleEndSession() {
        try {
            const res = await apiFetch(`/room/${currentRoomCode}/quit`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
            })
            if (res.ok) {
                const data = await res.json()
                console.log("Session ended", data)
                setCurrentRoomCode(null)
            }
        } catch (err) {
            console.error("Error quitting room:", err)
        }
    }

    return (
        <>
            <div className="swipe-header">
                <div className="mode-badge">Solo</div>
                <button className="show-watched hide-watched">Show Watched</button>
                <div className="genres">Genres</div>
            </div>

            <div className="swipe-main">
                <div className="swipe-deck">
                    {visibleCards.map((movie, index) => (
                        <MovieCard 
                            key={movie.media_id}
                            card={movie}
                            isTopCard={index === visibleCards.length - 1}
                            setDragX={setDragX}
                            zIndex={index}
                        />
                    ))}
                </div>
                
                

                <button className="undo-button">Undo</button>
                <p className="movie-instructions">Tap poster for full details</p>
            </div>

            <div className="swipe-footer">
                <button className="end-session" onClick={handleEndSession}>End Session</button>
                <button className="shortlist">Shortlist</button>
            </div>

            <div className="glow glow-left" style={{ opacity: leftOpacity }}></div>
            <div className="glow glow-right" style={{ opacity: rightOpacity }}></div>
        </>
    )
}