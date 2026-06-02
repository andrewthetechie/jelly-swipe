import React from "react"
import JoinModal from "./JoinModal"
import HostModal from "./HostModal"
import { useRoomContext } from "./RoomContextProvider"
import type { JSX } from "react"


export default function Intro(): JSX.Element {
    const [showJoinModal, setShowJoinModal] = React.useState<boolean>(false)
    const [showHostModal, setShowHostModal] = React.useState<boolean>(false)
    const { setMovies, setTvShows, setIsSoloMode, setUserInputCode } = useRoomContext()
    

    function handleSessionClick(e: React.MouseEvent<HTMLButtonElement>) {
        const sessionType: string | undefined = e.currentTarget.dataset.sessionType
        // console.log(sessionType)
        if (sessionType === "host") {
            setShowHostModal(true)
        } else if (sessionType === "join") {
            setShowJoinModal(true)
        }
    }

    function handleModalClose(e: React.MouseEvent<HTMLDivElement>) {
        const modalType: string | undefined = e.currentTarget.dataset.modalType
        // console.log(modalType)
        if (modalType === "host") {
            setShowHostModal(false)
            setMovies(true)
            setTvShows(false)
            setIsSoloMode(false)
        } else if (modalType === "join") {
            setShowJoinModal(false)
            setUserInputCode("")
        }
    }

    return (
        <div className="button-container">
            <button className="jelly-button" onClick={handleSessionClick} data-session-type="host">Host <br /> Session</button>
            <button className="jelly-button" onClick={handleSessionClick} data-session-type="join">Join <br /> Session</button>
            {showJoinModal && <JoinModal onClose={handleModalClose} />}
            {showHostModal && <HostModal onClose={handleModalClose} />}
        </div>
    )
}