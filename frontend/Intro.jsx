import React from "react"
import JoinModal from "./JoinModal"
import HostModal from "./HostModal"
import { RoomContext } from "./App"


export default function Intro() {
    const [showJoinModal, setShowJoinModal] = React.useState(false)
    const [showHostModal, setShowHostModal] = React.useState(false)
    const { movies, setMovies, tvShows, setTvShows, isSoloMode, setIsSoloMode, userInputCode, setUserInputCode } = React.useContext(RoomContext)
    

    function handleSessionClick(e) {
        const sessionType = e.target.dataset.sessionType
        // console.log(sessionType)
        if (sessionType === "host") {
            setShowHostModal(true)
        } else if (sessionType === "join") {
            setShowJoinModal(true)
        }
    }

    function handleModalClose(e) {
        const modalType = e.target.dataset.modalType
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