import React from 'react'
import { useRoomStateContext, useRoomSetterContext } from "./RoomContextProvider"
import type { JSX } from "react"
import { joinRoom } from './roomApi'

interface JoinModalProps {
    onClose: React.MouseEventHandler<HTMLButtonElement | HTMLDivElement>
}

export default function JoinModal({ onClose }: JoinModalProps): JSX.Element {
    const { userInputCode } = useRoomStateContext()
    const { setCurrentRoomCode, setUserInputCode } = useRoomSetterContext()
    const [isSubmitting, setIsSubmitting] = React.useState<boolean>(false)
    const isValid = userInputCode.length === 4

    async function doJoin() {
        if (!isValid) return
        if (isSubmitting) return
        setIsSubmitting(true)
        
        try {
            await joinRoom(userInputCode)
            setCurrentRoomCode(userInputCode)            
        } catch (err) {
            console.error("Error joining room:", err)
        } finally {
            setIsSubmitting(false)
        }
    }
    return (
        <div className="modal">
            <div className="modal-inner">
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
            <button className="modal-button" onClick={doJoin} disabled={isSubmitting || !isValid}>
                {isSubmitting ? "Joining Session..." : "Join Session"}
            </button>
            <button className="modal-button" onClick={onClose} data-modal-type="join">Cancel</button>
            </div>
        </div>
    )
}