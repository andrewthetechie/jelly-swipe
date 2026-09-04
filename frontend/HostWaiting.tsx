import { useRoomStateContext } from "./RoomContextProvider"
import logo from "./assets/logo.png"
import sad from "./assets/sad.png"
import type { JSX } from "react"

interface HostWaitingProps {
    endSession: () => Promise<void>
}

export default function HostWaiting({ endSession }: HostWaitingProps): JSX.Element {
    const { currentRoomCode } = useRoomStateContext()

    return (
        <div className="host-waiting">
            <h1 className="room-code-block">
                <span className="room-code-label">Room Code</span>
                <span className="room-code" data-testid="room-code">{currentRoomCode}</span>
            </h1>

            <p className="waiting-text">
                Waiting for partner...
            </p>

            <div className="waiting-logo-container">
                <img src={logo} alt="" />
                <img src={sad} alt=""/>
            </div>

            <button className="end-session" onClick={endSession}>End Session</button>

        </div>
    )
}
