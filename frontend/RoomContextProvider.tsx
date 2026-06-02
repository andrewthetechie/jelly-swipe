import React from "react"

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

interface RoomProviderProps {
    children: React.ReactNode
}

export function RoomContextProvider({ children }: RoomProviderProps) {
    const [currentRoomCode, setCurrentRoomCode] = React.useState<string | null>(null)
    const [movies, setMovies] = React.useState<boolean>(true)
    const [tvShows, setTvShows] = React.useState<boolean>(false)
    const [isSoloMode, setIsSoloMode] = React.useState<boolean>(false)
    const [userInputCode, setUserInputCode] = React.useState<string>("")

    return (
        <RoomContext.Provider 
            value={{ 
                currentRoomCode, 
                setCurrentRoomCode, 
                movies, 
                setMovies, 
                tvShows, 
                setTvShows, 
                isSoloMode, 
                setIsSoloMode, 
                userInputCode, 
                setUserInputCode 
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