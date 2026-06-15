import React from "react"
import Header from "./Header"
import { useRoomContext } from "./RoomContextProvider"
import logo from "./assets/logo.png"
import sad from "./assets/sad.png"
import type { JSX } from "react"

interface HostWaitingProps {
    endSession: () => Promise<void>
}

export default function HostWaiting({ endSession }: HostWaitingProps): JSX.Element {
    const { currentRoomCode } = useRoomContext()

    return (
        <div className="host-waiting">
            <h1>Room Code: {currentRoomCode}</h1>
            
            <p className="waiting-text">
                Waiting for partner...
            </p>

            <div className="waiting-logo-container">
                <img src={logo} />
                <img src={sad} />
            </div>

            <button className="end-session" onClick={endSession}>End Session</button>
        
        </div>
    )
}
