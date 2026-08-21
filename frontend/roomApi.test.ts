import { afterEach, describe, expect, it, vi } from "vitest"
import * as api from "./api"
import {
    RoomApiError,
    createRoom,
    joinRoom,
    quitRoom,
    fetchDeck,
    postSwipe,
    undoSwipe,
    setGenreChoice,
    setWatchedFilter,
    fetchGenres,
    fetchCast,
    fetchMatches,
} from "./roomApi"

function okResponse(body: unknown = {}): Response {
    return new Response(JSON.stringify(body), {
        status: 200,
        statusText: "OK",
        headers: { "Content-Type": "application/json" },
    })
}

function errorResponse(status: number, statusText: string): Response {
    return new Response(null, { status, statusText })
}

afterEach(() => {
    vi.restoreAllMocks()
})

// ---------------------------------------------------------------------------
// RoomApiError
// ---------------------------------------------------------------------------

describe("RoomApiError", () => {
    it("carries status and statusText", () => {
        const err = new RoomApiError(404, "Not Found", "testing")
        expect(err.status).toBe(404)
        expect(err.statusText).toBe("Not Found")
        expect(err.name).toBe("RoomApiError")
        expect(err.message).toContain("404")
    })
})

// ---------------------------------------------------------------------------
// createRoom
// ---------------------------------------------------------------------------

describe("createRoom", () => {
    it("POSTs to /room with snake_case body", async () => {
        const spy = vi
            .spyOn(api, "postJson")
            .mockResolvedValue(okResponse({ pairing_code: "1234" }))

        const result = await createRoom({ movies: true, tvShows: false, solo: true })

        expect(spy).toHaveBeenCalledWith("/room", {
            movies: true,
            tv_shows: false,
            solo: true,
        })
        expect(result).toEqual({ pairing_code: "1234" })
    })

    it("rejects with RoomApiError on !res.ok", async () => {
        vi.spyOn(api, "postJson").mockResolvedValue(errorResponse(422, "Unprocessable Entity"))

        await expect(createRoom({ movies: true, tvShows: true, solo: false })).rejects.toSatisfy(
            (e: unknown) =>
                e instanceof RoomApiError && e.status === 422 && e.statusText === "Unprocessable Entity",
        )
    })
})

// ---------------------------------------------------------------------------
// joinRoom
// ---------------------------------------------------------------------------

describe("joinRoom", () => {
    it("POSTs to /room/:code/join", async () => {
        const spy = vi
            .spyOn(api, "postJson")
            .mockResolvedValue(okResponse({ status: "joined" }))

        const result = await joinRoom("ABCD")

        expect(spy).toHaveBeenCalledWith("/room/ABCD/join")
        expect(result).toEqual({ status: "joined" })
    })

    it("rejects with RoomApiError on !res.ok", async () => {
        vi.spyOn(api, "postJson").mockResolvedValue(errorResponse(403, "Forbidden"))

        await expect(joinRoom("ABCD")).rejects.toSatisfy(
            (e: unknown) => e instanceof RoomApiError && e.status === 403,
        )
    })
})

// ---------------------------------------------------------------------------
// quitRoom
// ---------------------------------------------------------------------------

describe("quitRoom", () => {
    it("POSTs to /room/:code/quit", async () => {
        const spy = vi
            .spyOn(api, "postJson")
            .mockResolvedValue(okResponse({ status: "quit" }))

        await quitRoom("ABCD")

        expect(spy).toHaveBeenCalledWith("/room/ABCD/quit")
    })

    it("rejects with RoomApiError on !res.ok", async () => {
        vi.spyOn(api, "postJson").mockResolvedValue(errorResponse(404, "Not Found"))

        await expect(quitRoom("ABCD")).rejects.toSatisfy(
            (e: unknown) => e instanceof RoomApiError && e.status === 404,
        )
    })
})

// ---------------------------------------------------------------------------
// fetchDeck
// ---------------------------------------------------------------------------

describe("fetchDeck", () => {
    it("GETs /room/:code/deck", async () => {
        const deck = [{ media_id: "abc", title: "Film" }]
        const spy = vi
            .spyOn(api, "apiFetch")
            .mockResolvedValue(okResponse(deck))

        const result = await fetchDeck("ABCD")

        const [path] = spy.mock.calls[0] as [string, RequestInit]
        expect(path).toBe("/room/ABCD/deck")
        expect(result).toMatchObject([{mediaId: "abc", title: "Film"}])
    })

    it("rejects with RoomApiError on !res.ok", async () => {
        vi.spyOn(api, "apiFetch").mockResolvedValue(errorResponse(500, "Internal Server Error"))

        await expect(fetchDeck("ABCD")).rejects.toSatisfy(
            (e: unknown) => e instanceof RoomApiError && e.status === 500,
        )
    })
})

// ---------------------------------------------------------------------------
// postSwipe
// ---------------------------------------------------------------------------

describe("postSwipe", () => {
    it("POSTs to /room/:code/swipe with media_id and direction", async () => {
        const spy = vi
            .spyOn(api, "postJson")
            .mockResolvedValue(okResponse())

        await postSwipe("ABCD", "item-1", "right")

        expect(spy).toHaveBeenCalledWith("/room/ABCD/swipe", {
            media_id: "item-1",
            direction: "right",
        })
    })

    it("rejects with RoomApiError on !res.ok", async () => {
        vi.spyOn(api, "postJson").mockResolvedValue(errorResponse(400, "Bad Request"))

        await expect(postSwipe("ABCD", "item-1", "left")).rejects.toSatisfy(
            (e: unknown) => e instanceof RoomApiError && e.status === 400,
        )
    })
})

// ---------------------------------------------------------------------------
// undoSwipe
// ---------------------------------------------------------------------------

describe("undoSwipe", () => {
    it("POSTs to room/:code/undo with media_id", async () => {
        const spy = vi
            .spyOn(api, "postJson")
            .mockResolvedValue(okResponse())

        await undoSwipe("ABCD", "item-1")

        expect(spy).toHaveBeenCalledWith("room/ABCD/undo", { media_id: "item-1" })
    })

    it("rejects with RoomApiError on !res.ok", async () => {
        vi.spyOn(api, "postJson").mockResolvedValue(errorResponse(404, "Not Found"))

        await expect(undoSwipe("ABCD", "item-1")).rejects.toSatisfy(
            (e: unknown) => e instanceof RoomApiError && e.status === 404,
        )
    })
})

// ---------------------------------------------------------------------------
// setGenreChoice
// ---------------------------------------------------------------------------

describe("setGenreChoice", () => {
    it("POSTs to /room/:code/genre with genre", async () => {
        const deck = [{ media_id: "x", title: "X" }]
        const spy = vi
            .spyOn(api, "postJson")
            .mockResolvedValue(okResponse(deck))

        const result = await setGenreChoice("ABCD", "Horror")

        expect(spy).toHaveBeenCalledWith("/room/ABCD/genre", { genre: "Horror" })
        expect(result).toMatchObject([{ mediaId: "x", title: "X" }])
    })

    it("rejects with RoomApiError on !res.ok", async () => {
        vi.spyOn(api, "postJson").mockResolvedValue(errorResponse(400, "Bad Request"))

        await expect(setGenreChoice("ABCD", "Horror")).rejects.toSatisfy(
            (e: unknown) => e instanceof RoomApiError && e.status === 400,
        )
    })
})

// ---------------------------------------------------------------------------
// setWatchedFilter
// ---------------------------------------------------------------------------

describe("setWatchedFilter", () => {
    it("POSTs to /room/:code/watched-filter with hide_watched", async () => {
        const deck = [{ media_id: "y", title: "Y" }]
        const spy = vi
            .spyOn(api, "postJson")
            .mockResolvedValue(okResponse(deck))

        const result = await setWatchedFilter("ABCD", true)

        expect(spy).toHaveBeenCalledWith("/room/ABCD/watched-filter", { hide_watched: true })
        expect(result).toMatchObject([{ mediaId: "y", title: "Y" }])
    })

    it("rejects with RoomApiError on !res.ok", async () => {
        vi.spyOn(api, "postJson").mockResolvedValue(errorResponse(400, "Bad Request"))

        await expect(setWatchedFilter("ABCD", false)).rejects.toSatisfy(
            (e: unknown) => e instanceof RoomApiError && e.status === 400,
        )
    })
})

// ---------------------------------------------------------------------------
// fetchGenres
// ---------------------------------------------------------------------------

describe("fetchGenres", () => {
    it("GETs /genres", async () => {
        const genres = ["Action", "Comedy"]
        const spy = vi
            .spyOn(api, "apiFetch")
            .mockResolvedValue(okResponse(genres))

        const result = await fetchGenres()

        const [path] = spy.mock.calls[0] as [string, RequestInit]
        expect(path).toBe("/genres")
        expect(result).toEqual(genres)
    })

    it("rejects with RoomApiError on !res.ok", async () => {
        vi.spyOn(api, "apiFetch").mockResolvedValue(errorResponse(502, "Bad Gateway"))

        await expect(fetchGenres()).rejects.toSatisfy(
            (e: unknown) => e instanceof RoomApiError && e.status === 502,
        )
    })
})

// ---------------------------------------------------------------------------
// fetchCast
// ---------------------------------------------------------------------------

describe("fetchCast", () => {
    it("GETs /cast/:mediaId", async () => {
        const castData = { cast: [{ name: "Alice", character: "Hero" }] }
        const spy = vi
            .spyOn(api, "apiFetch")
            .mockResolvedValue(okResponse(castData))

        const result = await fetchCast("media-123")

        const [path] = spy.mock.calls[0] as [string, RequestInit]
        expect(path).toBe("/cast/media-123")
        expect(result).toEqual(castData)
    })

    it("forwards the AbortSignal", async () => {
        const spy = vi
            .spyOn(api, "apiFetch")
            .mockResolvedValue(okResponse({ cast: [] }))

        const controller = new AbortController()
        await fetchCast("media-123", controller.signal)

        const [, options] = spy.mock.calls[0] as [string, RequestInit]
        expect(options.signal).toBe(controller.signal)
    })

    it("rejects with RoomApiError on !res.ok", async () => {
        vi.spyOn(api, "apiFetch").mockResolvedValue(errorResponse(404, "Not Found"))

        await expect(fetchCast("media-123")).rejects.toSatisfy(
            (e: unknown) => e instanceof RoomApiError && e.status === 404,
        )
    })
})

// ---------------------------------------------------------------------------
// fetchMatches
// ---------------------------------------------------------------------------

describe("fetchMatches", () => {
    it("GETs /matches and unwraps .matches array", async () => {
        const matches = [
            { title: "Film A", posterUrl: null, media_id: "1", media_type: "movie", deep_link: null, rating: null, duration: null, year: null },
        ]
        const spy = vi
            .spyOn(api, "apiFetch")
            .mockResolvedValue(okResponse({ matches }))

        const result = await fetchMatches()

        const [path] = spy.mock.calls[0] as [string, RequestInit]
        expect(path).toBe("/matches")
        expect(result).toMatchObject(
            [{ title: "Film A", posterUrl: null, mediaId: "1", mediaType: "movie", deepLink: null, rating: null, duration: null, year: null }]
        )
    })

    it("returns an empty array when .matches is empty", async () => {
        vi.spyOn(api, "apiFetch").mockResolvedValue(okResponse({ matches: [] }))

        const result = await fetchMatches()
        expect(result).toEqual([])
    })

    it("rejects with RoomApiError on !res.ok", async () => {
        vi.spyOn(api, "apiFetch").mockResolvedValue(errorResponse(401, "Unauthorized"))

        await expect(fetchMatches()).rejects.toSatisfy(
            (e: unknown) => e instanceof RoomApiError && e.status === 401 && e.statusText === "Unauthorized",
        )
    })
})
