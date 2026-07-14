import React from "react"
import { apiFetch } from "./api"
import { useRoomContext } from "./RoomContextProvider"
import type { GenreListResponse } from "./types"
import type { JSX } from "react"

// const genreList: GenreListResponse = [
//     "Action",
//     "Adventure",
//     "Animation",
//     "Biography",
//     "Comedy",
//     "Crime",
//     "Documentary",
//     "Drama",
//     "Family",
//     "Horror",
//     "Kids",
//     "Mystery",
//     "Reality",
//     "Romance",
//     "Sci-Fi",
//     "Thriller",
//     "Western"
// ]

interface GenreModalProps {
    handleGenreClick: () => void
    handleGenreChange: () => void
}

export default function GenreModal({ handleGenreClick, handleGenreChange }: GenreModalProps): JSX.Element {
    const [genreList, setGenreList] = React.useState<GenreListResponse>(() => {
        const cached = sessionStorage.getItem("genres")
        return cached ? JSON.parse(cached) : []
    })
    const { genre, setGenre } = useRoomContext()

    React.useEffect(() => {
        const cached = sessionStorage.getItem("genres")
        if (cached) {
            setGenreList(JSON.parse(cached))
            return
        }

        const fetchGenres = async () => {
            try {
                const res: Response = await apiFetch(`/genres`, {
                    method: 'GET',
                    headers: {'Content-Type': 'application/json'},
                })
                if (!res.ok) {
                    throw new Error(`Error fetching genres: ${res.status} ${res.statusText}`)
                }

                const data = await res.json()
                setGenreList(data)
                sessionStorage.setItem("genres", JSON.stringify(data))
            } catch (err) {
                console.error("Error fetching genres:", err)
            }
        }
        fetchGenres()
    }, [])

    const genreElements = genreList.map((option) => (
        <label 
            className={`custom-radio ${genre === option ? "active" : ""}`}
            key={option} 
            htmlFor={option}
        >
            <input 
                type="radio"
                id={option}
                name="genre"
                value={option}
                checked={genre === option}
                onChange={(e) => setGenre(e.target.value)}
            />
            {option}
        </label>
    ))

    return (
        <div className="modal">
            <div className="modal-inner modal-genre">
                <h2 className="card-item-title">Select Genre</h2>
                <div className="genre-inputs">
                    {genreElements}
                </div>
                <button className="modal-button" onClick={handleGenreChange}>Confirm</button>
                <button className="modal-button" onClick={handleGenreClick}>Cancel</button>
            </div>
        </div>
    )
}