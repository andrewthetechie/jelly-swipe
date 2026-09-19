import React from 'react'
import { useRoomStateContext, useRoomSetterContext } from "./RoomContextProvider"
import type { JSX } from "react"
import { joinRoom, RoomApiError } from './roomApi'
import FormError from "./FormError"
import Modal from "./Modal"

interface JoinModalProps {
    onClose: () => void
}

export default function JoinModal({ onClose }: JoinModalProps): JSX.Element {
    const { userInputCode } = useRoomStateContext()
    const { setCurrentRoomCode, setUserInputCode } = useRoomSetterContext()
    const [isSubmitting, setIsSubmitting] = React.useState<boolean>(false)
    const [error, setError] = React.useState<string | null>(null)
    const isValid = userInputCode.length === 4

    async function doJoin() {
        if (!isValid) return
        if (isSubmitting) return
        setIsSubmitting(true)
        setError(null)

        try {
            await joinRoom(userInputCode)
            setCurrentRoomCode(userInputCode)
        } catch (err) {
            console.error("Error joining room:", err)
            if (err instanceof RoomApiError && err.status === 404) {
                setError("That room code isn't active. Check the code with your partner and try again.")
            } else {
                setError("Couldn't reach the server. Check your connection and try again.")
            }
        } finally {
            setIsSubmitting(false)
        }
    }
    return (
        <Modal onClose={onClose} labelledBy="join-modal-heading">
            <h2 id="join-modal-heading">Enter Room Code</h2>
            <label htmlFor="roomCode">Room Code</label>
            <input
                id="roomCode"
                type="text"
                inputMode="numeric"
                minLength={4}
                maxLength={4}
                placeholder="0000"
                className="room-code-input"
                value={userInputCode}
                onChange={(e) => { setUserInputCode(e.target.value.replace(/[^0-9]/g, '')); setError(null) }}
            />
            <button className="btn-primary" onClick={doJoin} disabled={isSubmitting || !isValid}>
                {isSubmitting ? "Joining Session..." : "Join Session"}
            </button>
            <button className="btn-secondary" onClick={onClose}>Cancel</button>
            <FormError message={error} />
        </Modal>
    )
}
