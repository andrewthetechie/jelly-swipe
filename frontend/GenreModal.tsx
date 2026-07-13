import React from "react"
import { apiFetch } from "./api"
import type { GenreListResponse } from "./types"

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
    genre: string,
    setGenre: React.Dispatch<React.SetStateAction<string>>,
    handleGenreClick: () => void
}

export default function GenreModal({ genre, setGenre, handleGenreClick }: GenreModalProps) {
    const [genreList, setGenreList] = React.useState<GenreListResponse>([])
    React.useEffect(() => {
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
                console.log(data)
                setGenreList(data)

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
                <button className="modal-button">Confirm</button>
                <button className="modal-button" onClick={handleGenreClick}>Cancel</button>
            </div>
        </div>
    )
}