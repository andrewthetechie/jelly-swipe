import React from 'react'
import { useRoomContext } from "./RoomContextProvider"
import { apiFetch } from "./api"
import type { JSX } from "react"

interface JoinModalProps {
    onClose: React.MouseEventHandler<HTMLButtonElement | HTMLDivElement>
}

export default function JoinModal({ onClose }: JoinModalProps): JSX.Element {
    const { setCurrentRoomCode, userInputCode, setUserInputCode } = useRoomContext()

    async function joinRoom() {
        try {
            const res: Response = await apiFetch(`/room/${userInputCode}/join`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'}
            })
            if (res.ok) {
                const data: { status: string } = await res.json()
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
                minLength={4}
                maxLength={4}
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