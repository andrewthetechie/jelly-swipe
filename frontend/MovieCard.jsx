import React from 'react'
import { actorElements } from "./assets/test-info"
import moanaPoster from "./assets/moana-poster.jpg"
import sadLogo from "./assets/sad.png"
import { apiUrl } from "./api"

export default function MovieCard({ cardDeck }) {
    console.log("MovieCard received cardDeck:", cardDeck)

    const sampleCard = cardDeck.length ? cardDeck[0] : {} 
    const { duration, media_id: mediaId, media_type: mediaType, rating, season_count, summary, thumb, title, year } = cardDeck.length ? sampleCard : {}
    const mediaText = mediaType === "movie" ? "Movie" : mediaType === "tv_show" ? "TV" : ""
    const seasonsText = season_count === 1 ? ` • ${season_count} Season` : season_count > 1 ? ` • ${season_count} Seasons` : ""
    const [showDetails, setShowDetails] = React.useState(false)
    const toggleDetails = () => {
        setShowDetails(prev => !prev)
    } 

    return (
        <div className={`movie-card-container ${showDetails ? "flipped" : ""}`} onClick={toggleDetails}>
            {sampleCard && (
                 <div className="movie-card-inner">
                    <div className="movie-card front">
                        <div className="media-type">{mediaText}{seasonsText}</div>
                        <img src={thumb ? apiUrl(thumb).toString() : sadLogo} alt={title} className="movie-poster" />
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
                            <button className="watch-trailer">WATCH TRAILER</button>
                        </div>
                        <p className="movie-description">
                            {summary}
                        </p>
                        <div className="movie-cast">
                            {actorElements}
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}