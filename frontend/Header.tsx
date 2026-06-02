import React from 'react'
import nameLogo from './assets/name-logo.png'
import { useRoomContext } from "./RoomContextProvider"
import type { JSX } from "react"

export default function Header(): JSX.Element {
    const { currentRoomCode } = useRoomContext()
    return (
        <header className="app-header">
            {!currentRoomCode && <img src={nameLogo} alt="Jelly-Swipe logo" className="app-logo" />}
        </header>
    );
}