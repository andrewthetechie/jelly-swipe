import React from "react"
import type { GenreListResponse } from "./types"
import { G } from "vitest/dist/chunks/reporters.nr4dxCkA.js"

const genreList: GenreListResponse = [
    "Action",
    "Adventure",
    "Animation",
    "Biography",
    "Comedy",
    "Crime",
    "Documentary",
    "Drama",
    "Family",
    "Horror",
    "Kids",
    "Mystery",
    "Reality",
    "Romance",
    "Sci-Fi",
    "Thriller",
    "Western"
]

interface GenreModalProps {
    genre: string,
    setGenre: React.Dispatch<React.SetStateAction<string>>,
    handleGenreClick: () => void
}

export default function GenreModal({ genre, setGenre, handleGenreClick }: GenreModalProps) {
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
            <div className="modal-inner">
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