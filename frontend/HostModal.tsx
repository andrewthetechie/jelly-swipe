import React from "react"
import { useRoomStateContext, useRoomSetterContext } from "./RoomContextProvider"
import type { JSX } from "react"
import { createRoom } from "./roomApi"

interface HostModalProps {
    onClose: React.MouseEventHandler<HTMLButtonElement | HTMLDivElement>
}

export default function HostModal({ onClose }: HostModalProps): JSX.Element {
    const { movies, tvShows, isSoloMode } = useRoomStateContext()
    const { setMovies, setTvShows, setIsSoloMode, setCurrentRoomCode } = useRoomSetterContext()
    const [isSubmitting, setIsSubmitting] = React.useState<boolean>(false)

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

    async function doCreate() {
        if (isSubmitting) return
        setIsSubmitting(true)

        try {
            const { pairing_code } = await createRoom({
                movies, tvShows, solo: isSoloMode
            })
            setCurrentRoomCode(pairing_code)
        } catch (err) {
            console.error("Error creating session:", err)
        } finally {
            setIsSubmitting(false)
        }

    }

    return (
        <div className="modal">
            <div className="modal-inner">
                <h2>Session Setup</h2>
                
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

                <button className="modal-button" onClick={doCreate} disabled={isSubmitting}>
                    {isSubmitting ? "Creating Session..." : "Create Session"}
                </button>
                <button className="modal-button" onClick={onClose} data-modal-type="host">Cancel</button>
            </div>
        </div>
    )
}