import React from 'react'
import { actorElements } from "./assets/test-info"
import moanaPoster from "./assets/moana-poster.jpg"

export default function MovieCard({ cardDeck }) {
    console.log("MovieCard received cardDeck:", cardDeck)
    // duration: "1h 41m"
    // media_id: "9a6e1465f40c98ec2f28b2f1d1f588b8"
    // media_type: "movie"
    // rating: 5.516
    // season_count: null
    // summary: "In order to escape the police after a robbery, two estranged siblings lay low in a metaphysical farmhouse that hides them away in a different time. There they reckon with a mysterious force that pushes their familial bonds to unnatural breaking points."
    // thumb: "/proxy?path=jellyfin/9a6e1465f40c98ec2f28b2f1d1f588b8/Primary"
    // title: "Things Will Be Different"
    // year: 2024

    const [showDetails, setShowDetails] = React.useState(false)

    const toggleDetails = () => {
        setShowDetails(prev => !prev)
    } 

    return (
        <div className={`movie-card-container ${showDetails ? "flipped" : ""}`} onClick={toggleDetails}>
            <div className="movie-card-inner">
                    <div className="movie-card front">
                        <div className="media-type">Movie</div>
                        <img src={moanaPoster} alt="Moana poster" className="movie-poster" />
                    </div>

                    <div className="movie-card back">
                        <h2 className="movie-title">Moana</h2>
                        <div className="movie-info">
                            <div className="movie-score">IMDb 7.6</div>
                            <div className="movie-runtime">1h 47m</div>
                            <div className="movie-year">2016</div>
                        </div>
                        <div className="trailer">
                            <button className="watch-trailer">WATCH TRAILER</button>
                        </div>
                        <p className="movie-description">
                            An adventurous teenager sails out on a daring mission to save her people. During her journey, 
                            Moana meets the once-mighty demigod Maui, who guides her in her quest to become a master wayfinder.
                        </p>
                        <div className="movie-cast">
                            {actorElements}
                        </div>
                    </div>
            </div>
        </div>
    )
}