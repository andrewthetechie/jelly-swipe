/* eslint-disable react-hooks/set-state-in-effect */

import Intro from "./Intro"
import SwipePage from "./SwipePage"
import { useRoomStateContext } from "./RoomContextProvider"
import type { JSX } from "react"

export default function Main(): JSX.Element {
    const { currentRoomCode } = useRoomStateContext()
  
    return (
        <main>
            {!currentRoomCode ? <Intro /> : <SwipePage />}
        </main>
    )
}