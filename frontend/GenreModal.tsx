import React from "react"
import type { GenreListResponse } from "./types"
import type { JSX } from "react"
import { fetchGenres } from "./roomApi"
import { useRoomSession } from "./RoomSessionProvider"
import FormError from "./FormError"
import Modal from "./Modal"

interface GenreModalProps {
    onClose: () => void
}

export default function GenreModal({ onClose }: GenreModalProps): JSX.Element {
    const [genreList, setGenreList] = React.useState<GenreListResponse>(() => {
        try {
            const cached = sessionStorage.getItem("genres")
            const parsed = cached ? JSON.parse(cached) : null
            return Array.isArray(parsed) && parsed.every(g => typeof g === "string") ? parsed : []
        } catch {
            return []
        }
    })

    const { state, confirmGenre } = useRoomSession()
    const [pendingGenre, setPendingGenre] = React.useState<string>(state.genre)
    const [error, setError] = React.useState<string | null>(null)

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
                setError("Couldn't load genres. Check your connection and try again.")
            }
        }
        fetchGenreList()
    }, [genreList.length])

    const genreElements = genreList.map((option) => (
        <label
            className={`custom-radio ${pendingGenre === option ? "active" : ""}`}
            key={option}
            htmlFor={option}
        >
            <input
                type="radio"
                id={option}
                name="genre"
                value={option}
                checked={pendingGenre === option}
                onChange={(e) => { setPendingGenre(e.target.value); setError(null) }}
            />
            {option}
        </label>
    ))

    const handleConfirm = async () => {
        const succeeded = await confirmGenre(pendingGenre)
        if (succeeded) {
            onClose()
        } else {
            // Keep the modal open so the failure is visible where the user
            // is looking; the banner behind the modal stays as the global record.
            setError("Couldn't change the genre. Check your connection and try again.")
        }
    }

    return (
        <Modal onClose={onClose} labelledBy="genre-modal-heading" className="modal-genre">
            <h2 id="genre-modal-heading">Select Genre</h2>
            <div className="genre-inputs">
                {genreElements}
            </div>
            <button className="modal-button" onClick={handleConfirm}>Confirm</button>
            <button className="modal-button" onClick={onClose}>Cancel</button>
            <FormError message={error} />
        </Modal>
    )
}
