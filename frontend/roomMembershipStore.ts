import { RoomApiError } from "./roomApi"

export interface RoomMembershipApi {
    createRoom(options: { movies: boolean; tvShows: boolean; solo: boolean }): Promise<{ pairing_code: string }>
    joinRoom(roomCode: string): Promise<{ status: string }>
}

export interface RoomMembershipStoreDeps {
    api: RoomMembershipApi
    setCurrentRoomCode: (code: string | null) => void
    setMovies: (value: boolean) => void
    setTvShows: (value: boolean) => void
    setIsSoloMode: (value: boolean) => void
    setUserInputCode: (value: string) => void
}

interface RoomMembershipState {
    isSubmitting: boolean
    error: string | null
}

export const CREATE_FAILED_MESSAGE = "Couldn't start the session. Check that Jelly-Swipe can reach your Jellyfin server."
export const JOIN_CODE_NOT_ACTIVE_MESSAGE = "That room code isn't active. Check the code with your partner and try again."
export const JOIN_REACHABILITY_MESSAGE = "Couldn't reach the server. Check your connection and try again."

/** The code-entry validity rule: exactly 4 digits. Pure helper for forms to apply to the current input value. */
export function isValidRoomCode(code: string): boolean {
    return /^[0-9]{4}$/.test(code)
}

/**
 * Plain (non-React) store for the room-entry command layer: the create/join
 * commands, their pending/error state, the error-message mapping, and the
 * code-entry policy. It sits IN FRONT of the existing RoomContextProvider
 * setters — it forwards through them via the constructor deps and does NOT own
 * the five room states (those live in RoomContextProvider).
 */
export class RoomMembershipStore {
    private state: RoomMembershipState
    private readonly api: RoomMembershipApi
    private readonly _setCurrentRoomCode: (code: string | null) => void
    private readonly _setMovies: (value: boolean) => void
    private readonly _setTvShows: (value: boolean) => void
    private readonly _setIsSoloMode: (value: boolean) => void
    private readonly _setUserInputCode: (value: string) => void
    private readonly listeners = new Set<() => void>()

    constructor(deps: RoomMembershipStoreDeps) {
        this.api = deps.api
        this._setCurrentRoomCode = deps.setCurrentRoomCode
        this._setMovies = deps.setMovies
        this._setTvShows = deps.setTvShows
        this._setIsSoloMode = deps.setIsSoloMode
        this._setUserInputCode = deps.setUserInputCode
        this.state = { isSubmitting: false, error: null }
    }

    getState(): RoomMembershipState {
        return this.state
    }

    subscribe(listener: () => void): () => void {
        this.listeners.add(listener)
        return () => {
            this.listeners.delete(listener)
        }
    }

    /** Begin a fresh entry on modal open: clear any stale error. Leaves isSubmitting and the setup fields untouched. */
    beginEntry(): void {
        this.patchState({ error: null })
    }

    /** Create a room and, on success, forward the response's pairing_code exactly once. */
    async create(options: { movies: boolean; tvShows: boolean; solo: boolean }): Promise<void> {
        if (this.state.isSubmitting) return
        this.patchState({ isSubmitting: true, error: null })
        try {
            const response = await this.api.createRoom(options)
            this._setCurrentRoomCode(response.pairing_code)
        } catch (err) {
            console.error("Error creating session:", err)
            this.patchState({ error: CREATE_FAILED_MESSAGE })
        } finally {
            this.patchState({ isSubmitting: false })
        }
    }

    /** Join a room by typed code and, on success, forward the typed code exactly once. */
    async join(code: string): Promise<void> {
        if (!isValidRoomCode(code)) return
        if (this.state.isSubmitting) return
        this.patchState({ isSubmitting: true, error: null })
        try {
            await this.api.joinRoom(code)
            this._setCurrentRoomCode(code)
        } catch (err) {
            console.error("Error joining room:", err)
            if (err instanceof RoomApiError && err.status === 404) {
                this.patchState({ error: JOIN_CODE_NOT_ACTIVE_MESSAGE })
            } else {
                this.patchState({ error: JOIN_REACHABILITY_MESSAGE })
            }
        } finally {
            this.patchState({ isSubmitting: false })
        }
    }

    /** Code-entry policy: strip non-digits preserving order, forward, and clear the shown join error. */
    applyCodeInput(raw: string): void {
        this._setUserInputCode(raw.replace(/[^0-9]/g, ""))
        this.patchState({ error: null })
    }

    setMovies(value: boolean): void {
        this._setMovies(value)
    }

    setTvShows(value: boolean): void {
        this._setTvShows(value)
    }

    setIsSoloMode(value: boolean): void {
        this._setIsSoloMode(value)
    }

    /** Reset the host setup to the defaults declared in RoomContextProvider's state initialization. */
    resetHostSetup(): void {
        this._setMovies(true)
        this._setTvShows(false)
        this._setIsSoloMode(false)
    }

    /** Clear the typed join code. */
    resetJoinInput(): void {
        this._setUserInputCode("")
    }

    /** Leave the room: clear only the room code. Must NOT reset setup state. */
    leave(): void {
        this._setCurrentRoomCode(null)
    }

    /** Merge a partial state patch and notify listeners. */
    private patchState(patch: Partial<RoomMembershipState>): void {
        this.state = { ...this.state, ...patch }
        this.listeners.forEach((listener) => listener())
    }
}
