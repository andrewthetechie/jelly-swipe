import React from "react"
import logo from "./assets/logo.png"
import moanaPoster from "./assets/moana-poster.jpg"
import { apiUrl } from "./api"
import type { JSX } from "react"
import type { MatchItem } from "./types"

interface MatchFoundModalProps {
    onClick: () => void
    matchItem: MatchItem
}

export default function MatchFoundModal({ onClick, matchItem }: MatchFoundModalProps): JSX.Element {
    console.log("matchItem:", matchItem)
    const { title, thumb, media_id: mediaId, media_type: mediaType, deep_link: deepLink, rating, duration, year }: MatchItem = matchItem
    return (
        <div className="modal">
            <div className="modal-inner">
                <img src={logo} className="match-logo" />
                <h2>It's a match!</h2>
                <img src={apiUrl(thumb).toString()} className="match-poster" />
                <h3 className="match-title">{title}</h3>
                <div className="card-item-info match-info">
                    <div className="card-item-score">IMDb {Number(rating).toFixed(2)}</div>
                    <div className="card-item-runtime">{duration}</div>
                    <div className="card-item-year">{year}</div>
                </div>
                <a href={deepLink ? deepLink : "#"} target="_blank" rel="noopener noreferrer" className="modal-button modal-button-link">
                    Open in Jellyfin 🍿
                </a>
                <button className="modal-button" onClick={onClick}>Keep Swiping</button>
            </div>
        </div>
    )
}

// still needs testing
// need to update css queries to adjust for mid-size screens - mobile and desktop are okay but ipad does not look good