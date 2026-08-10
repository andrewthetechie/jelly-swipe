import React from "react"
import { useRoomStateContext, useRoomSetterContext } from "./RoomContextProvider"
import { postJson } from "./api"
import type { JSX } from "react"

interface HostModalProps {
    onClose: React.MouseEventHandler<HTMLButtonElement | HTMLDivElement>
}

export default function HostModal({ onClose }: HostModalProps): JSX.Element {
    const { movies, tvShows, isSoloMode } = useRoomStateContext()
    const { setMovies, setTvShows, setIsSoloMode, setCurrentRoomCode } = useRoomSetterContext()

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

    async function createSession() {
        let pairingCode: string | null = null

        try {
            const res: Response = await postJson('/room', { 
                movies,
                "tv_shows": tvShows,
                "solo": isSoloMode, 
            })
            
            if (!res.ok) {
                throw new Error(`Error creating session: ${res.status} ${res.statusText}`)
            }
            
            const createRoomResponse: { pairing_code: string } = await res.json()
            pairingCode = createRoomResponse.pairing_code
            setCurrentRoomCode(createRoomResponse.pairing_code)
        } catch (err) {
            console.error("Error creating session:", err)
        }

    }

    return (
        <div className="modal">
            <div className="modal-inner">
                <h2>Session Setup</h2>
                
                <label htmlFor="movies" className="jelly-toggle"> 
                    <span>Movies</span>
                    <input type="checkbox" id="movies" name="movies" value="movies" defaultChecked={movies} onChange={handleChange} />
                    <span className="slider"></span>
                </label>
                
                <label htmlFor="tvShows" className="jelly-toggle"> 
                    <span>TV Shows</span>
                    <input type="checkbox" id="tvShows" name="tvShows" value="tvShows" defaultChecked={tvShows} onChange={handleChange} />
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
        </div>
    )
}