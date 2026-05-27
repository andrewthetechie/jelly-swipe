import React from 'react'
import { RoomContext } from './App'
import { apiFetch } from "./api"

export default function JoinModal({ onClose }) {
    const { currentRoomCode, setCurrentRoomCode } = React.useContext(RoomContext)
    const { userInputCode, setUserInputCode } = React.useContext(RoomContext)

    async function joinRoom() {
        try {
            const res = await apiFetch(`/room/${userInputCode}/join`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'}
            })
            if (res.ok) {
                const data = await res.json()
                setCurrentRoomCode(userInputCode)
                console.log(`Joined room ${userInputCode}:`, data)
            }
        } catch (err) {
            console.error("Error joining room:", err)
        }
    }
    return (
        <div className="join-modal modal">
            <h2>Enter Room Code</h2>
            <input 
                type="text"
                inputMode="numeric" 
                minLength="4"
                maxLength="4"
                placeholder="Enter Host Code" 
                className="room-code-input" 
                value={userInputCode} 
                onChange={(e) => setUserInputCode(e.target.value.replace(/[^0-9]/g, ''))} 
            />
            <button className="modal-button" onClick={joinRoom}>Join Session</button>
            <button className="modal-button" onClick={onClose} data-modal-type="join">Cancel</button>
        </div>
    )
}