/* eslint-disable react-refresh/only-export-components */

import React from "react"
import * as roomApi from "./roomApi"
import { RoomMembershipStore } from "./roomMembershipStore"

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

export interface RoomMembershipContextType {
    isSubmitting: boolean
    error: string | null
    create: (options: { movies: boolean; tvShows: boolean; solo: boolean }) => Promise<void>
    join: (code: string) => Promise<void>
    beginEntry: () => void
    applyCodeInput: (raw: string) => void
    setMovies: (value: boolean) => void
    setTvShows: (value: boolean) => void
    setIsSoloMode: (value: boolean) => void
    resetHostSetup: () => void
    resetJoinInput: () => void
    leave: () => void
}

interface RoomProviderProps {
    children: React.ReactNode
}

const RoomStateContext = React.createContext<RoomStateContextType | undefined>(undefined)

const RoomSetterContext = React.createContext<RoomSetterContextType | undefined>(undefined)

const RoomMembershipContext = React.createContext<RoomMembershipContextType | undefined>(undefined)

export function useRoomMembership() {
    const context = React.useContext(RoomMembershipContext)

    if (context === undefined) {
        throw new Error("useRoomMembership must be used within a RoomContextProvider")
    }

    return context
}

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

    // Create the membership store once per mount. `api` defaults to the module
    // import so existing `vi.mock("./roomApi")` suites keep intercepting store
    // calls; setters are stable React setState fns, so toggle forwarding works
    // even when RoomStateSeeder sets state in useLayoutEffect after mount.
    const [{ store, subscribe, getState }] = React.useState(() => {
        const store = new RoomMembershipStore({
            api: roomApi,
            setCurrentRoomCode,
            setMovies,
            setTvShows,
            setIsSoloMode,
            setUserInputCode,
        })
        return {
            store,
            subscribe: (listener: () => void) => store.subscribe(listener),
            getState: () => store.getState(),
        }
    })

    const membershipState = React.useSyncExternalStore(subscribe, getState)

    // Stable identity so mount effects in the entry modals can depend on it
    // without re-firing on every error/submitting change.
    const beginEntry = React.useCallback(() => {
        store.beginEntry()
    }, [store])

    const roomMembershipValue = React.useMemo<RoomMembershipContextType>(() => ({
        isSubmitting: membershipState.isSubmitting,
        error: membershipState.error,
        create: (options) => store.create(options),
        join: (code) => store.join(code),
        beginEntry,
        applyCodeInput: (raw) => store.applyCodeInput(raw),
        setMovies: (value) => store.setMovies(value),
        setTvShows: (value) => store.setTvShows(value),
        setIsSoloMode: (value) => store.setIsSoloMode(value),
        resetHostSetup: () => store.resetHostSetup(),
        resetJoinInput: () => store.resetJoinInput(),
        leave: () => store.leave(),
    }), [membershipState.isSubmitting, membershipState.error, store, beginEntry])

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
        <RoomMembershipContext.Provider value={roomMembershipValue}>
            <RoomSetterContext.Provider value={roomSetterValue}>
                <RoomStateContext.Provider value={roomStateValue}>
                    {children}
                </RoomStateContext.Provider>
            </RoomSetterContext.Provider>
        </RoomMembershipContext.Provider>
    )
}
