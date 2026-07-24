import React from "react"
import { apiFetch } from "./api"
import { matchListSample } from "./assets/test-info"

export default function MatchListModal() {

    // const handleMatchList = React.useCallback(async () => {
    //         console.log("Match List")
    //         try {
    //             const res: Response = await apiFetch('/matches', {
    //                 method: 'GET',
    //                 headers: {'Content-Type': 'application/json'},
    //             })
    //             if (!res.ok) {
    //                 throw new Error(`Error retrieving matches: ${res.status} ${res.statusText}`)
    //             }
    //             const data = await res.json()
    //             console.log("matches data:", data.matches)
    //         } catch (err) {
    //             console.error("Error retrieving matches:", err)
    //         }
    //     }, [])

    const matchElements = matchListSample.map((match) => {
        const { 
            title, 
            thumb, 
            media_id: mediaId, 
            media_type: mediaType, 
            deep_link: deepLink, 
            rating, 
            duration, 
            year 
        } = match
        
        return (
            <div className="match-list-item" key={mediaId}>
                <img src={thumb} className="match-list-img" />
                <div className="match-list-info">
                    <h3 className="match-list-title">{title}</h3>
                    {rating && <div className="match-list-score">IMDb {Number(rating).toFixed(2)}</div>}
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
                <div className="match-list-container">
                    {matchElements}
                </div>
            </div>
        </div>
    )
}