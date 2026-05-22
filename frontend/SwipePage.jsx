import React from "react"
import MovieCard from "./MovieCard"

export default function SwipePage( {cardDeck} ) {
    

    return (
        <>
            <div className="swipe-header">
                <div className="mode-badge">Solo</div>
                <button className="show-watched hide-watched">Show Watched</button>
                <div className="genres">Genres</div>
            </div>

            <div className="swipe-main">
                <MovieCard cardDeck={cardDeck} />

                <button className="undo-button">Undo</button>
                <p className="movie-instructions">Tap poster for full details</p>
            </div>

            <div className="swipe-footer">
                <button className="end-session">End Session</button>
                <button className="shortlist">Shortlist</button>
            </div>
        </>
    )
}