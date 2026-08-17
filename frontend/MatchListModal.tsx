import React from "react"
import { apiUrl, apiFetch } from "./api"
import { formatRating } from './format'
import type { JSX } from "react"
import sadLogo from "./assets/sad.png"
import type { MatchItem } from "./types"

interface MatchListModalProps {
    handleMatchListClick: () => void
}

export default function MatchListModal({ handleMatchListClick }: MatchListModalProps): JSX.Element {
    const [matchList, setMatchList] = React.useState<MatchItem[]>([])

    React.useEffect(() => {
        async function fetchMatchList() {
            try {
                const res: Response = await apiFetch('/matches', {
                    method: 'GET',
                    headers: {'Content-Type': 'application/json'},
                })
                if (!res.ok) {
                    throw new Error(`Error retrieving matches: ${res.status} ${res.statusText}`)
                }
                const data = await res.json()
                setMatchList(data.matches)
            } catch (err) {
                console.error("Error retrieving matches:", err)
            }
        }
        fetchMatchList()
    }, [])

    const matchElements = matchList.map((match) => {
        const { 
            title, 
            thumb, 
            media_id: mediaId, 
            deep_link: deepLink, 
            rating, 
            duration, 
            year 
        } = match

        return (
            <div className="match-list-item" key={mediaId}>
                <img src={thumb ? apiUrl(thumb).toString(): sadLogo} alt={title ?? ""} className="match-list-img" />
                <div className="match-list-info">
                    <h3 className="match-list-title">{title}</h3>
                    {rating && <div className="match-list-score">IMDb {formatRating(rating)}</div>}
                    {duration && <div className="match-list-runtime">{duration}</div>}
                    <div className="match-list-year">{year}</div>
                    <a href={deepLink ? deepLink : "#"} target="_blank" rel="noopener noreferrer" className="match-list-button">
                        Open in Jellyfin 🍿
                    </a>
                </div>
            </div>
        )
    })

    return (
        <div className="modal">
            <div className="modal-inner modal-match-list">
                <h2>Match List</h2>
                {matchList.length === 0 && <h3 className="jelly-check">No Matches Yet!</h3>}
                <div className="match-list-container">
                    {matchElements}
                </div>
                <button className="modal-button" onClick={handleMatchListClick}>Keep Swiping</button>
            </div>
        </div>
    )
}