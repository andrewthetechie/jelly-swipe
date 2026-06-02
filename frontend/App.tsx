import React from "react"
import Main from "./Main"
import Header from "./Header"
import { RoomContextProvider } from "./RoomContextProvider" 

interface RoomContextType {
    currentRoomCode: string | null
    setCurrentRoomCode: React.Dispatch<React.SetStateAction<string | null>>
    movies: boolean
    setMovies: React.Dispatch<React.SetStateAction<boolean>>
    tvShows: boolean
    setTvShows: React.Dispatch<React.SetStateAction<boolean>>
    isSoloMode: boolean
    setIsSoloMode: React.Dispatch<React.SetStateAction<boolean>>
    userInputCode: string
    setUserInputCode: React.Dispatch<React.SetStateAction<string>>
}
const RoomContext = React.createContext<RoomContextType | undefined>(undefined)

export default function App() {


    return (
        <RoomContextProvider>
            <Header />
            <Main />
        </RoomContextProvider>
    )
}

export { RoomContext }