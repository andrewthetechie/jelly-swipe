import React from "react"
import JoinModal from "./JoinModal"
import HostModal from "./HostModal"
import { useRoomMembership } from "./RoomContextProvider"
import type { JSX } from "react"


export default function Intro(): JSX.Element {
    const [showJoinModal, setShowJoinModal] = React.useState<boolean>(false)
    const [showHostModal, setShowHostModal] = React.useState<boolean>(false)
    const membership = useRoomMembership()


    function handleSessionClick(e: React.MouseEvent<HTMLButtonElement>) {
        const sessionType: string | undefined = e.currentTarget.dataset.sessionType
        if (sessionType === "host") {
            setShowHostModal(true)
        } else if (sessionType === "join") {
            setShowJoinModal(true)
        }
    }

    function closeHostModal() {
        setShowHostModal(false)
        membership.resetHostSetup()
    }

    function closeJoinModal() {
        setShowJoinModal(false)
        membership.resetJoinInput()
    }

    return (
        <div className="button-container">
            <button className="jelly-button" onClick={handleSessionClick} data-session-type="host">Host <br /> Session</button>
            <button className="jelly-button" onClick={handleSessionClick} data-session-type="join">Join <br /> Session</button>
            {showJoinModal && <JoinModal onClose={closeJoinModal} />}
            {showHostModal && <HostModal onClose={closeHostModal} />}
        </div>
    )
}
