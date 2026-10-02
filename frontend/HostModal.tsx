import React from "react"
import { useRoomMembership, useRoomStateContext } from "./RoomContextProvider"
import type { JSX } from "react"
import FormError from "./FormError"
import Modal from "./Modal"

interface HostModalProps {
    onClose: () => void
}

export default function HostModal({ onClose }: HostModalProps): JSX.Element {
    const { movies, tvShows, isSoloMode } = useRoomStateContext()
    const { isSubmitting, error, create, beginEntry, setMovies, setTvShows, setIsSoloMode } = useRoomMembership()

    // On each open (mount), start with a clean error so a stale failure from a
    // previous session never renders in this modal.
    React.useEffect(() => {
        beginEntry()
    }, [beginEntry])

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const { name, checked } = e.currentTarget
        if (name === "movies") {
            setMovies(checked)
        } else if (name === "tvShows") {
            setTvShows(checked)
        } else if (name === "solo") {
            setIsSoloMode(checked)
        }
    }

    function doCreate() {
        create({ movies, tvShows, solo: isSoloMode })
    }

    return (
        <Modal onClose={onClose} labelledBy="host-modal-heading">
            <h2 id="host-modal-heading">Session Setup</h2>

            <label htmlFor="movies" className="jelly-toggle">
                <span>Movies</span>
                <input type="checkbox" id="movies" name="movies" value="movies" checked={movies} onChange={handleChange} />
                <span className="slider"></span>
            </label>

            <label htmlFor="tvShows" className="jelly-toggle">
                <span>TV Shows</span>
                <input type="checkbox" id="tvShows" name="tvShows" value="tvShows" checked={tvShows} onChange={handleChange} />
                <span className="slider"></span>
            </label>

            <label htmlFor="solo" className="jelly-toggle solo">
                <span>Solo</span>
                <input type="checkbox" id="solo" name="solo" value="solo" checked={isSoloMode} onChange={handleChange} />
                <span className="slider"></span>
            </label>

            <button className="btn-primary" onClick={doCreate} disabled={isSubmitting}>
                {isSubmitting ? "Creating Session..." : "Create Session"}
            </button>
            <button className="btn-secondary" onClick={onClose}>Cancel</button>
            <FormError message={error} />
        </Modal>
    )
}
