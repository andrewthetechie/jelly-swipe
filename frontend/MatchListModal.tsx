import React from "react"
import { apiFetch } from "./api"

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

    return (
        <div className="modal">
            <div className="modal-inner">
                <h2 className="card-item-title">Match List</h2>
            </div>
        </div>
    )
}