/* eslint-disable react-refresh/only-export-components */

import React from "react"

export interface RoomStateContextType {
    currentRoomCode: string | null
    roomReady: boolean
    movies: boolean
    tvShows: boolean
    isSoloMode: boolean
    userInputCode: string
    genre: string
    hideWatched: boolean
}

export interface RoomSetterContextType {
    setCurrentRoomCode: React.Dispatch<React.SetStateAction<string | null>>
    setRoomReady: React.Dispatch<React.SetStateAction<boolean>>
    setMovies: React.Dispatch<React.SetStateAction<boolean>>
    setTvShows: React.Dispatch<React.SetStateAction<boolean>>
    setIsSoloMode: React.Dispatch<React.SetStateAction<boolean>>
    setUserInputCode: React.Dispatch<React.SetStateAction<string>>
    setGenre: React.Dispatch<React.SetStateAction<string>>
    setHideWatched: React.Dispatch<React.SetStateAction<boolean>>
}

interface RoomProviderProps {
    children: React.ReactNode
}

export const RoomStateContext = React.createContext<RoomStateContextType | undefined>(undefined)

export const RoomSetterContext = React.createContext<RoomSetterContextType | undefined>(undefined)

export function useRoomStateContext() {
    const context = React.useContext(RoomStateContext)

    if (context === undefined) {
        throw new Error("useRoomStateContext must be used within a RoomContextProvider")
    }
    
    return context
}

export function useRoomSetterContext() {
    const context = React.useContext(RoomSetterContext)

    if (context === undefined) {
        throw new Error("useRoomSetterContext must be used within a RoomContextProvider")
    }
    
    return context
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

    const roomStateValue = React.useMemo(() => ({
        currentRoomCode,
        roomReady,
        movies,
        tvShows,
        isSoloMode,
        userInputCode,
        genre,
        hideWatched
    }), 
    [
        currentRoomCode,
        roomReady,
        movies,
        tvShows,
        isSoloMode,
        userInputCode,
        genre,
        hideWatched
    ])

    const roomSetterValue = React.useMemo(() => ({
        setCurrentRoomCode,
        setRoomReady,
        setMovies,
        setTvShows,
        setIsSoloMode,
        setUserInputCode,
        setGenre,
        setHideWatched
    }), [])

    return (
        <RoomSetterContext.Provider value={roomSetterValue}> 
            <RoomStateContext.Provider value={roomStateValue}>
                {children}
            </RoomStateContext.Provider>
        </RoomSetterContext.Provider>
    )
}