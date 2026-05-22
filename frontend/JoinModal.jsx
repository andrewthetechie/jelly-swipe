import React from 'react'
import { RoomContext } from './App'

export default function JoinModal({ onClose }) {
    const { currentRoomCode, setCurrentRoomCode } = React.useContext(RoomContext)
    const { userInputCode, setUserInputCode } = React.useContext(RoomContext)
    return (
        <div className="join-modal modal">
            <h2>Enter Room Code</h2>
            <input 
                type="text"
                inputMode="numeric" 
                placeholder="Enter Host Code" 
                className="room-code-input" 
                value={userInputCode} 
                onChange={(e) => setUserInputCode(e.target.value.replace(/[^0-9]/g, ''))} 
            />
            <button className="modal-button">Join Session</button>
            <button className="modal-button" onClick={onClose} data-modal-type="join">Cancel</button>
        </div>
    )
}