import React from "react"
import { useRoomStateContext, useRoomMembership } from "./RoomContextProvider"
import type { JSX } from "react"
import { isValidRoomCode } from "./roomMembershipStore"
import FormError from "./FormError"
import Modal from "./Modal"

interface JoinModalProps {
    onClose: () => void
}

export default function JoinModal({ onClose }: JoinModalProps): JSX.Element {
    const { userInputCode } = useRoomStateContext()
    const { isSubmitting, error, join, beginEntry, applyCodeInput } = useRoomMembership()
    const isValid = isValidRoomCode(userInputCode)

    // On each open (mount), start with a clean error so a stale failure from a
    // previous session never renders in this modal.
    React.useEffect(() => {
        beginEntry()
    }, [beginEntry])

    function doJoin() {
        join(userInputCode)
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
                onChange={(e) => applyCodeInput(e.target.value)}
            />
            <button className="btn-primary" onClick={doJoin} disabled={isSubmitting || !isValid}>
                {isSubmitting ? "Joining Session..." : "Join Session"}
            </button>
            <button className="btn-secondary" onClick={onClose}>Cancel</button>
            <FormError message={error} />
        </Modal>
    )
}
