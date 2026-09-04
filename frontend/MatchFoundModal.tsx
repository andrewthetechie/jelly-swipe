import logo from "./assets/logo.png"
import PosterImage from "./PosterImage"
import { formatRating } from './format'
import type { JSX } from "react"
import type { MatchItem } from "./types"

interface MatchFoundModalProps {
    onClick: () => void
    matchItem: MatchItem
}

export default function MatchFoundModal({ onClick, matchItem }: MatchFoundModalProps): JSX.Element {
    const { title, posterUrl, deepLink, rating, duration, year }: MatchItem = matchItem
    return (
        <div className="modal">
            <div className="modal-inner">
                <img src={logo} className="match-logo" alt="Jelly-Swipe logo" />
                <h2 className="match-headline">It's a match!</h2>
                <PosterImage posterUrl={posterUrl} alt={title ?? ""} className="match-poster" />
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
