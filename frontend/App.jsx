import React from "react"
import Main from "./Main"
import Header from "./Header"

const RoomContext = React.createContext()

export default function App() {
    const [currentRoomCode, setCurrentRoomCode] = React.useState(null)
    const [movies, setMovies] = React.useState(true)
    const [tvShows, setTvShows] = React.useState(false)
    const [isSoloMode, setIsSoloMode] = React.useState(false)
    const [userInputCode, setUserInputCode] = React.useState("")

    return (
        <RoomContext.Provider value={{ currentRoomCode, setCurrentRoomCode, movies, setMovies, tvShows, setTvShows, isSoloMode, setIsSoloMode, userInputCode, setUserInputCode }}>
            {!currentRoomCode && <Header />}
            <Main />
        </RoomContext.Provider>
    )
}

export { RoomContext }