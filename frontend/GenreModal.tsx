import React from "react"
import type { GenreListResponse } from "./types"
import type { JSX } from "react"
import { fetchGenres } from "./roomApi"
import { useRoomSession } from "./RoomSessionProvider"

interface GenreModalProps {
    handleGenreClick: () => void
}

export default function GenreModal({ handleGenreClick }: GenreModalProps): JSX.Element {
    const [genreList, setGenreList] = React.useState<GenreListResponse>(() => {
        try {
            const cached = sessionStorage.getItem("genres")
            const parsed = cached ? JSON.parse(cached) : null
            return Array.isArray(parsed) && parsed.every(g => typeof g === "string") ? parsed : []
        } catch {
            return []
        }
    })

    const { state, selectGenre, confirmGenre } = useRoomSession()

    React.useEffect(() => {
        if (genreList.length > 0) {
            return
        }

        const fetchGenreList = async () => {
            try {
                const data = await fetchGenres()
                setGenreList(data)
                sessionStorage.setItem("genres", JSON.stringify(data))
            } catch (err) {
                console.error("Error fetching genres:", err)
            }
        }
        fetchGenreList()
    }, [genreList.length])

    const genreElements = genreList.map((option) => (
        <label
            className={`custom-radio ${state.genre === option ? "active" : ""}`}
            key={option}
            htmlFor={option}
        >
            <input
                type="radio"
                id={option}
                name="genre"
                value={option}
                checked={state.genre === option}
                onChange={(e) => selectGenre(e.target.value)}
            />
            {option}
        </label>
    ))

    return (
        <div className="modal">
            <div className="modal-inner modal-genre">
                <h2>Select Genre</h2>
                <div className="genre-inputs">
                    {genreElements}
                </div>
                <button className="modal-button" onClick={confirmGenre}>Confirm</button>
                <button className="modal-button" onClick={async () => { await confirmGenre(); handleGenreClick() }}>Cancel</button>
            </div>
        </div>
    )
}
