import { describe, expect, it, vi } from "vitest"
import { RoomApiError } from "./roomApi"
import {
    CREATE_FAILED_MESSAGE,
    JOIN_CODE_NOT_ACTIVE_MESSAGE,
    JOIN_REACHABILITY_MESSAGE,
    RoomMembershipStore,
    isValidRoomCode,
    type RoomMembershipApi,
} from "./roomMembershipStore"

interface RoomMembershipSetters {
    setCurrentRoomCode: (code: string | null) => void
    setMovies: (value: boolean) => void
    setTvShows: (value: boolean) => void
    setIsSoloMode: (value: boolean) => void
    setUserInputCode: (value: string) => void
}

function makeApi(overrides: Partial<RoomMembershipApi> = {}): RoomMembershipApi {
    return {
        createRoom: vi.fn(),
        joinRoom: vi.fn(),
        ...overrides,
    }
}

function makeSetters(): RoomMembershipSetters {
    return {
        setCurrentRoomCode: vi.fn(),
        setMovies: vi.fn(),
        setTvShows: vi.fn(),
        setIsSoloMode: vi.fn(),
        setUserInputCode: vi.fn(),
    }
}

function makeStore(
    api: RoomMembershipApi,
    setters: RoomMembershipSetters = makeSetters(),
) {
    return new RoomMembershipStore({ api, ...setters })
}

describe("RoomMembershipStore create command", () => {
    it("forwards the response pairing_code exactly once on success", async () => {
        const api = makeApi({
            createRoom: vi.fn().mockResolvedValue({ pairing_code: "1234" }),
        })
        const setters = makeSetters()
        const store = makeStore(api, setters)

        await store.create({ movies: true, tvShows: false, solo: true })

        expect(api.createRoom).toHaveBeenCalledWith({ movies: true, tvShows: false, solo: true })
        expect(setters.setCurrentRoomCode).toHaveBeenCalledTimes(1)
        expect(setters.setCurrentRoomCode).toHaveBeenCalledWith("1234")
        expect(store.getState().isSubmitting).toBe(false)
        expect(store.getState().error).toBeNull()
    })

    it("sets the byte-identical fixed message on failure", async () => {
        const api = makeApi({ createRoom: vi.fn().mockRejectedValue(new Error("boom")) })
        const setters = makeSetters()
        const store = makeStore(api, setters)
        const errorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined)

        await store.create({ movies: true, tvShows: true, solo: false })

        expect(setters.setCurrentRoomCode).not.toHaveBeenCalled()
        expect(store.getState().error).toBe(CREATE_FAILED_MESSAGE)
        expect(store.getState().isSubmitting).toBe(false)
        errorSpy.mockRestore()
    })

    it("ignores a create while one is pending (double-submit guard)", async () => {
        let release: (r: { pairing_code: string }) => void = () => {}
        const api = makeApi({
            createRoom: vi.fn(() => new Promise<{ pairing_code: string }>((res) => { release = res })),
        })
        const setters = makeSetters()
        const store = makeStore(api, setters)

        const first = store.create({ movies: true, tvShows: false, solo: true })
        const second = store.create({ movies: true, tvShows: true, solo: false })
        release({ pairing_code: "1111" })
        await first
        await second

        expect(api.createRoom).toHaveBeenCalledTimes(1)
        expect(setters.setCurrentRoomCode).toHaveBeenCalledTimes(1)
    })

    it("clears a shown create error on a new submit", async () => {
        const api = makeApi({
            createRoom: vi.fn()
                .mockRejectedValueOnce(new Error("boom"))
                .mockResolvedValue({ pairing_code: "1234" }),
        })
        const setters = makeSetters()
        const store = makeStore(api, setters)
        const errorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined)

        await store.create({ movies: true, tvShows: false, solo: true })
        expect(store.getState().error).toBe(CREATE_FAILED_MESSAGE)

        await store.create({ movies: true, tvShows: false, solo: true })

        expect(store.getState().error).toBeNull()
        expect(setters.setCurrentRoomCode).toHaveBeenCalledTimes(1)
        errorSpy.mockRestore()
    })

    it("does not clear the create error on a toggle change", async () => {
        const api = makeApi({ createRoom: vi.fn().mockRejectedValue(new Error("boom")) })
        const setters = makeSetters()
        const store = makeStore(api, setters)
        const errorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined)
        await store.create({ movies: true, tvShows: false, solo: true })
        expect(store.getState().error).toBe(CREATE_FAILED_MESSAGE)

        store.setMovies(true)

        expect(store.getState().error).toBe(CREATE_FAILED_MESSAGE)
        expect(setters.setMovies).toHaveBeenCalledWith(true)
        errorSpy.mockRestore()
    })
})

describe("RoomMembershipStore join command", () => {
    it("forwards the typed code exactly once on success", async () => {
        const api = makeApi({ joinRoom: vi.fn().mockResolvedValue({ status: "joined" }) })
        const setters = makeSetters()
        const store = makeStore(api, setters)

        await store.join("1234")

        expect(api.joinRoom).toHaveBeenCalledWith("1234")
        expect(setters.setCurrentRoomCode).toHaveBeenCalledTimes(1)
        expect(setters.setCurrentRoomCode).toHaveBeenCalledWith("1234")
    })

    it("maps a 404 RoomApiError to the byte-identical invalid-code message", async () => {
        const api = makeApi({
            joinRoom: vi.fn().mockRejectedValue(new RoomApiError(404, "Not Found", "joining room")),
        })
        const setters = makeSetters()
        const store = makeStore(api, setters)
        const errorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined)

        await store.join("1234")

        expect(store.getState().error).toBe(JOIN_CODE_NOT_ACTIVE_MESSAGE)
        errorSpy.mockRestore()
    })

    it("maps any other failure to the byte-identical reachability message", async () => {
        const api = makeApi({ joinRoom: vi.fn().mockRejectedValue(new Error("network down")) })
        const setters = makeSetters()
        const store = makeStore(api, setters)
        const errorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined)

        await store.join("1234")

        expect(store.getState().error).toBe(JOIN_REACHABILITY_MESSAGE)
        errorSpy.mockRestore()
    })

    it("ignores a join with a code that is not exactly 4 digits", async () => {
        const api = makeApi()
        const setters = makeSetters()
        const store = makeStore(api, setters)

        await store.join("123")

        expect(api.joinRoom).not.toHaveBeenCalled()
        expect(setters.setCurrentRoomCode).not.toHaveBeenCalled()
    })

    it("ignores a join with a non-digit 4-char code", async () => {
        const api = makeApi()
        const setters = makeSetters()
        const store = makeStore(api, setters)

        await store.join("abcd")

        expect(api.joinRoom).not.toHaveBeenCalled()
        expect(setters.setCurrentRoomCode).not.toHaveBeenCalled()
    })

    it("clears a shown join error on a new submit", async () => {
        const api = makeApi({
            joinRoom: vi.fn()
                .mockRejectedValueOnce(new RoomApiError(404, "Not Found", "joining room"))
                .mockResolvedValue({ status: "joined" }),
        })
        const setters = makeSetters()
        const store = makeStore(api, setters)
        const errorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined)

        await store.join("1234")
        expect(store.getState().error).toBe(JOIN_CODE_NOT_ACTIVE_MESSAGE)

        await store.join("1234")

        expect(store.getState().error).toBeNull()
        expect(setters.setCurrentRoomCode).toHaveBeenCalledTimes(1)
        errorSpy.mockRestore()
    })

    it("ignores a join while one is pending (double-submit guard)", async () => {
        let release: (r: { status: string }) => void = () => {}
        const api = makeApi({
            joinRoom: vi.fn(() => new Promise<{ status: string }>((res) => { release = res })),
        })
        const setters = makeSetters()
        const store = makeStore(api, setters)

        const first = store.join("1234")
        const second = store.join("1234")
        release({ status: "joined" })
        await first
        await second

        expect(api.joinRoom).toHaveBeenCalledTimes(1)
        expect(setters.setCurrentRoomCode).toHaveBeenCalledTimes(1)
    })
})

describe("RoomMembershipStore code-entry policy", () => {
    it("strips non-digits preserving order and clears the shown join error", async () => {
        const api = makeApi({
            joinRoom: vi.fn().mockRejectedValue(new Error("network down")),
        })
        const setters = makeSetters()
        const store = makeStore(api, setters)
        const errorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined)
        await store.join("1234")
        expect(store.getState().error).toBe(JOIN_REACHABILITY_MESSAGE)

        store.applyCodeInput("a1b2c3d4")

        expect(setters.setUserInputCode).toHaveBeenCalledWith("1234")
        expect(store.getState().error).toBeNull()
        errorSpy.mockRestore()
    })

    it("isValidRoomCode requires exactly 4 digits", () => {
        expect(isValidRoomCode("1234")).toBe(true)
        expect(isValidRoomCode("123")).toBe(false)
        expect(isValidRoomCode("12345")).toBe(false)
        expect(isValidRoomCode("")).toBe(false)
        expect(isValidRoomCode("abcd")).toBe(false)
        expect(isValidRoomCode("12-4")).toBe(false)
    })
})

describe("RoomMembershipStore toggle and reset", () => {
    it("forwards movies, tvShows, and solo toggles", () => {
        const api = makeApi()
        const setters = makeSetters()
        const store = makeStore(api, setters)

        store.setMovies(false)
        store.setTvShows(true)
        store.setIsSoloMode(true)

        expect(setters.setMovies).toHaveBeenCalledWith(false)
        expect(setters.setTvShows).toHaveBeenCalledWith(true)
        expect(setters.setIsSoloMode).toHaveBeenCalledWith(true)
    })

    it("resetHostSetup forwards the declared defaults", () => {
        const api = makeApi()
        const setters = makeSetters()
        const store = makeStore(api, setters)

        store.resetHostSetup()

        expect(setters.setMovies).toHaveBeenCalledWith(true)
        expect(setters.setTvShows).toHaveBeenCalledWith(false)
        expect(setters.setIsSoloMode).toHaveBeenCalledWith(false)
    })

    it("resetJoinInput clears the typed code", () => {
        const api = makeApi()
        const setters = makeSetters()
        const store = makeStore(api, setters)

        store.resetJoinInput()

        expect(setters.setUserInputCode).toHaveBeenCalledWith("")
    })

    it("leave clears only currentRoomCode and not the setup state", () => {
        const api = makeApi()
        const setters = makeSetters()
        const store = makeStore(api, setters)

        store.leave()

        expect(setters.setCurrentRoomCode).toHaveBeenCalledTimes(1)
        expect(setters.setCurrentRoomCode).toHaveBeenCalledWith(null)
        expect(setters.setMovies).not.toHaveBeenCalled()
        expect(setters.setTvShows).not.toHaveBeenCalled()
        expect(setters.setIsSoloMode).not.toHaveBeenCalled()
        expect(setters.setUserInputCode).not.toHaveBeenCalled()
    })
})

describe("RoomMembershipStore subscription", () => {
    it("subscribe notifies listeners on state change", async () => {
        const api = makeApi({
            createRoom: vi.fn().mockResolvedValue({ pairing_code: "1234" }),
        })
        const setters = makeSetters()
        const store = makeStore(api, setters)
        const listener = vi.fn()
        store.subscribe(listener)

        await store.create({ movies: true, tvShows: false, solo: true })

        expect(listener).toHaveBeenCalled()
    })
})

describe("RoomMembershipStore beginEntry", () => {
    it("clears a shown error", async () => {
        const api = makeApi({
            createRoom: vi.fn().mockRejectedValue(new Error("boom")),
        })
        const setters = makeSetters()
        const store = makeStore(api, setters)
        const errorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined)

        await store.create({ movies: true, tvShows: false, solo: true })
        expect(store.getState().error).toBe(CREATE_FAILED_MESSAGE)

        store.beginEntry()

        expect(store.getState().error).toBeNull()
        errorSpy.mockRestore()
    })

    it("does not clear isSubmitting while a command is pending", async () => {
        let release: (r: { pairing_code: string }) => void = () => {}
        const api = makeApi({
            createRoom: vi.fn(() => new Promise<{ pairing_code: string }>((res) => { release = res })),
        })
        const setters = makeSetters()
        const store = makeStore(api, setters)

        const pending = store.create({ movies: true, tvShows: false, solo: true })
        expect(store.getState().isSubmitting).toBe(true)

        store.beginEntry()

        expect(store.getState().isSubmitting).toBe(true)
        release({ pairing_code: "1111" })
        await pending
    })
})
