import logo from "./assets/logo.png"
import sadLogo from "./assets/sad.png"
import { apiUrl, formatRating } from "./api"
import type { JSX } from "react"
import type { MatchItem } from "./types"

interface MatchFoundModalProps {
    onClick: () => void
    matchItem: MatchItem
}

export default function MatchFoundModal({ onClick, matchItem }: MatchFoundModalProps): JSX.Element {
    const { title, thumb, media_id: mediaId, media_type: mediaType, deep_link: deepLink, rating, duration, year }: MatchItem = matchItem
    return (
        <div className="modal">
            <div className="modal-inner">
                <img src={logo} className="match-logo" alt="Jelly-Swipe logo" />
                <h2>It's a match!</h2>
                <img src={thumb ? apiUrl(thumb).toString(): sadLogo} className="match-poster" alt={title ?? ""} />
                <h3 className="match-title">{title}</h3>
                <div className="card-item-info match-info">
                    {rating && <div className="card-item-score">IMDb {formatRating(rating)}</div>}
                    {duration && <div className="card-item-runtime">{duration}</div>}
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
