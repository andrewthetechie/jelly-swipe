/* eslint-disable react-refresh/only-export-components */

import React from "react"

export interface RoomStateContextType {
    currentRoomCode: string | null
    movies: boolean
    tvShows: boolean
    isSoloMode: boolean
    userInputCode: string
}

export interface RoomSetterContextType {
    setCurrentRoomCode: React.Dispatch<React.SetStateAction<string | null>>
    setMovies: React.Dispatch<React.SetStateAction<boolean>>
    setTvShows: React.Dispatch<React.SetStateAction<boolean>>
    setIsSoloMode: React.Dispatch<React.SetStateAction<boolean>>
    setUserInputCode: React.Dispatch<React.SetStateAction<string>>
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
    const [movies, setMovies] = React.useState<boolean>(true)
    const [tvShows, setTvShows] = React.useState<boolean>(false)
    const [isSoloMode, setIsSoloMode] = React.useState<boolean>(false)
    const [userInputCode, setUserInputCode] = React.useState<string>("")

    const roomStateValue = React.useMemo(() => ({
        currentRoomCode,
        movies,
        tvShows,
        isSoloMode,
        userInputCode,
    }), 
    [
        currentRoomCode,
        movies,
        tvShows,
        isSoloMode,
        userInputCode,
    ])

    const roomSetterValue = React.useMemo(() => ({
        setCurrentRoomCode,
        setMovies,
        setTvShows,
        setIsSoloMode,
        setUserInputCode,
    }), [])

    return (
        <RoomSetterContext.Provider value={roomSetterValue}> 
            <RoomStateContext.Provider value={roomStateValue}>
                {children}
            </RoomStateContext.Provider>
        </RoomSetterContext.Provider>
    )
}