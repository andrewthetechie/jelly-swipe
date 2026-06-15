import React from 'react'
import nameLogo from './assets/name-logo.png'
import { useRoomContext } from "./RoomContextProvider"
import type { JSX } from "react"

export default function Header(): JSX.Element {
    const { roomReady } = useRoomContext()
    return (
        <header className="app-header">
            {!roomReady && <img src={nameLogo} alt="Jelly-Swipe logo" className="app-logo" />}
        </header>
    )
}