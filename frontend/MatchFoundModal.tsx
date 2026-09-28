import logo from "./assets/logo.png"
import PosterImage from "./PosterImage"
import MediaFacts from "./MediaFacts"
import JellyfinDeepLink from "./JellyfinDeepLink"
import type { JSX } from "react"
import type { MatchItem } from "./types"
import Modal from "./Modal"

interface MatchFoundModalProps {
    onClose: () => void
    matchItem: MatchItem
}

export default function MatchFoundModal({ onClose, matchItem }: MatchFoundModalProps): JSX.Element {
    const { title, posterUrl, deepLink, rating, duration, year }: MatchItem = matchItem
    return (
        <Modal onClose={onClose} labelledBy="match-found-modal-heading">
            <img src={logo} className="match-logo" alt="Jelly-Swipe logo" />
            <h2 id="match-found-modal-heading" className="match-headline">It's a match!</h2>
            <PosterImage posterUrl={posterUrl} alt={title ?? ""} className="match-poster" />
            <h3 className="match-title">{title}</h3>
            <div className="card-item-info match-info">
                <MediaFacts rating={rating} duration={duration} year={year} scoreClassName="card-item-score" runtimeClassName="card-item-runtime" yearClassName="card-item-year" />
            </div>
            <JellyfinDeepLink deepLink={deepLink} className="btn-primary" linkClassName="btn-primary btn-primary-link" />
            <button className="btn-secondary" onClick={onClose}>Keep Swiping</button>
        </Modal>
    )
}
