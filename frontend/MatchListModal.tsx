import React from "react"
import { formatRating } from './format'
import type { JSX } from "react"
import PosterImage from "./PosterImage"
import type { MatchItem } from "./types"
import { fetchMatches } from "./roomApi"
import FormError from "./FormError"
import Modal from "./Modal"

interface MatchListModalProps {
    onClose: () => void
}

export default function MatchListModal({ onClose }: MatchListModalProps): JSX.Element {
    const [matchList, setMatchList] = React.useState<MatchItem[]>([])
    const [error, setError] = React.useState<string | null>(null)
    const [loaded, setLoaded] = React.useState<boolean>(false)

    React.useEffect(() => {
        async function fetchMatchList() {
            try {
                const matches = await fetchMatches()
                setMatchList(matches)
                setLoaded(true)
            } catch (err) {
                console.error("Error retrieving matches:", err)
                setError("Couldn't load your matches. Check your connection and try again.")
            }
        }
        fetchMatchList()
    }, [])

    const matchElements = matchList.map((match) => {
        const {
            title,
            posterUrl,
            mediaId,
            deepLink,
            rating,
            duration,
            year
        } = match

        return (
            <div className="match-list-item" key={mediaId}>
                <PosterImage posterUrl={posterUrl} alt={title ?? ""} className="match-list-img" />
                <div className="match-list-info">
                    <h3 className="match-list-title">{title}</h3>
                    {rating && <div className="match-list-score">IMDb {formatRating(rating)}</div>}
                    {duration && <div className="match-list-runtime">{duration}</div>}
                    <div className="match-list-year">{year}</div>
                    {deepLink
                        ? (
                            <a href={deepLink} target="_blank" rel="noopener noreferrer" className="btn-secondary match-list-button">
                                Open in Jellyfin 🍿
                            </a>
                        )
                        : (
                            <button type="button" className="btn-secondary match-list-button" disabled>
                                Open in Jellyfin 🍿
                            </button>
                        )}
                </div>
            </div>
        )
    })

    return (
        <Modal onClose={onClose} labelledBy="match-list-modal-heading" className="modal-match-list">
            <h2 id="match-list-modal-heading">Match List</h2>
            <FormError message={error} />
            {loaded && matchList.length === 0 && <h3 className="jelly-check">No Matches Yet!</h3>}
            <div className="match-list-container">
                {matchElements}
            </div>
            <button className="btn-secondary" onClick={onClose}>Keep Swiping</button>
        </Modal>
    )
}
