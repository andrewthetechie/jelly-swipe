import React from "react"
import { useRoomContext } from "./RoomContextProvider"
import { apiFetch } from "./api"
import type { JSX } from "react"

interface HostModalProps {
    onClose: React.MouseEventHandler<HTMLButtonElement | HTMLDivElement>
}

export default function HostModal({ onClose }: HostModalProps): JSX.Element {
    const { movies, setMovies, tvShows, setTvShows, isSoloMode, setIsSoloMode, setCurrentRoomCode } = useRoomContext()
    const roomOptions = {
            "movies": movies,
            "tv_shows": tvShows,
            "solo": isSoloMode
        }

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const { name, checked } = e.currentTarget
        if (name === "movies") {
            setMovies(checked)
        } else if (name === "tv") {
            setTvShows(checked)
        } else if (name === "solo") {
            setIsSoloMode(checked)
        }
        console.log(roomOptions)
    }

    async function createSession() {
        let fetchedCode: string | null = null
        try {
            const res: Response = await apiFetch('/room', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(roomOptions)
            })
            if (res.ok) {
                const data: { pairing_code: string } = await res.json()
                console.log("Session created with code:", data.pairing_code)
                fetchedCode = data.pairing_code
                setCurrentRoomCode(data.pairing_code)
                // data returns pairing_code and instance_id
            }

            

        } catch (err) {
            console.error("Error creating session:", err)
        }

    }

    return (
        <div className="host-modal modal">
            <h2>Session Setup</h2>
            
            <label htmlFor="movies" className="jelly-toggle"> 
                <span>Movies</span>
                <input type="checkbox" id="movies" name="movies" value="movies" defaultChecked={movies} onChange={handleChange} />
                <span className="slider"></span>
            </label>
            
            <label htmlFor="tv" className="jelly-toggle"> 
                <span>TV Shows</span>
                <input type="checkbox" id="tv" name="tv" value="tv" defaultChecked={tvShows} onChange={handleChange} />
                <span className="slider"></span>
            </label>
            
            <label htmlFor="solo" className="jelly-toggle solo"> 
                <span>Solo</span>
                <input type="checkbox" id="solo" name="solo" value="solo" defaultChecked={isSoloMode} onChange={handleChange} />
                <span className="slider"></span>
            </label>

            <button className="modal-button" onClick={createSession}>Create Session</button>
            <button className="modal-button" onClick={onClose} data-modal-type="host">Cancel</button>
        </div>
    )
}