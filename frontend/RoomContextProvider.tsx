import React from "react"

export interface RoomContextType {
    currentRoomCode: string | null
    setCurrentRoomCode: React.Dispatch<React.SetStateAction<string | null>>
    roomReady: boolean
    setRoomReady: React.Dispatch<React.SetStateAction<boolean>>
    movies: boolean
    setMovies: React.Dispatch<React.SetStateAction<boolean>>
    tvShows: boolean
    setTvShows: React.Dispatch<React.SetStateAction<boolean>>
    isSoloMode: boolean
    setIsSoloMode: React.Dispatch<React.SetStateAction<boolean>>
    userInputCode: string
    setUserInputCode: React.Dispatch<React.SetStateAction<string>>
    genre: string
    setGenre: React.Dispatch<React.SetStateAction<string>>
    hideWatched: boolean
    setHideWatched: React.Dispatch<React.SetStateAction<boolean>>
}

export const RoomContext = React.createContext<RoomContextType | undefined>(undefined)

interface RoomProviderProps {
    children: React.ReactNode
}

export function RoomContextProvider({ children }: RoomProviderProps) {
    const [currentRoomCode, setCurrentRoomCode] = React.useState<string | null>(null)
    const [roomReady, setRoomReady] = React.useState<boolean>(false)
    const [movies, setMovies] = React.useState<boolean>(true)
    const [tvShows, setTvShows] = React.useState<boolean>(false)
    const [isSoloMode, setIsSoloMode] = React.useState<boolean>(false)
    const [userInputCode, setUserInputCode] = React.useState<string>("")
    const [genre, setGenre] = React.useState<string>("All")
    const [hideWatched, setHideWatched] = React.useState<boolean>(false)

    return (
        <RoomContext.Provider
            value={{
                currentRoomCode,
                setCurrentRoomCode,
                roomReady,
                setRoomReady,
                movies,
                setMovies,
                tvShows,
                setTvShows,
                isSoloMode,
                setIsSoloMode,
                userInputCode,
                setUserInputCode,
                genre,
                setGenre,
                hideWatched,
                setHideWatched
        }}>
            {children}
        </RoomContext.Provider>
    )
}


export function useRoomContext() {
    const context = React.useContext(RoomContext)

    if (context === undefined) {
        throw new Error("useRoomContext must be used within a RoomContextProvider")
    }

    return context
}
