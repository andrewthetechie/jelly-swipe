import nameLogo from './assets/name-logo.png'
import type { JSX } from "react"
import { useRoomSession } from './RoomSessionProvider'

export default function Header(): JSX.Element {
    const { state } = useRoomSession()
    return (
        <header className="app-header">
            {!state.roomReady && <img src={nameLogo} alt="Jelly-Swipe logo" className="app-logo" />}
        </header>
    )
}