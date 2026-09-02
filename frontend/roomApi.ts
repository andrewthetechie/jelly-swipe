import { apiFetch, postJson } from "./api"
import { toCardItem, toMatchItem } from "./mediaAdapter"
import type { CardItemDto, MatchItemDto } from "./mediaAdapter"
import type {
    CardDeck,
    CastResponse,
    GenreListResponse,
    MatchItem,
    MutationChangeResult,
} from "./types"

export class RoomApiError extends Error {
    constructor(
        public readonly status: number,
        public readonly statusText: string,
        action: string,
    ) {
        super(`Error ${action}: ${status} ${statusText}`)
        this.name = "RoomApiError"
    }
}

async function ensureOk(res: Response, action: string): Promise<void> {
    if (!res.ok) {
        throw new RoomApiError(res.status, res.statusText, action)
    }
}

const GET_JSON: RequestInit = {
    method: "GET",
    headers: { "Content-Type": "application/json" },
}

// --- Room lifecycle ---

export async function createRoom(options: {
    movies: boolean
    tvShows: boolean
    solo: boolean
}): Promise<{ pairing_code: string}> {
    const res = await postJson("/room", {
        movies: options.movies,
        tv_shows: options.tvShows,
        solo: options.solo,
    })
    await ensureOk(res, "creating session")
    return res.json()
}

export async function joinRoom(roomCode: string): Promise<{ status: string }> {
    const res = await postJson(`/room/${roomCode}/join`)
    await ensureOk(res, "joining room")
    return res.json()
}

export async function quitRoom(roomCode: string): Promise<{ status: string }> {
    const res = await postJson(`/room/${roomCode}/quit`)
    await ensureOk(res, "quitting now")
    return res.json()
}

// --- Deck & swipes ---

export async function fetchDeck(roomCode: string): Promise<CardDeck> {
    const res = await apiFetch(`/room/${roomCode}/deck`, GET_JSON)
    await ensureOk(res, "fetching card deck")
    const raw: CardItemDto[] = await res.json()
    return raw.map(toCardItem)
}

export async function postSwipe(
    roomCode: string,
    mediaId: string,
    direction: "left" | "right"
): Promise<void> {
    const res = await postJson(`/room/${roomCode}/swipe`, {
        media_id: mediaId,
        direction,
    })
    await ensureOk(res, "POSTing swipe")
}

export async function undoSwipe(roomCode: string, mediaId: string): Promise<void> {
    const res = await postJson(`room/${roomCode}/undo`, { media_id: mediaId })
    await ensureOk(res, "undoing swipe")
}

// --- Room settings (POST returns the fresh deck) ---

async function parseMutationResponse(res: Response): Promise<MutationChangeResult> {
    const raw: {
        deck: CardItemDto[]
        mutation_event_id: number
        mutation_type: string
    } = await res.json()
    return {
        deck: raw.deck.map(toCardItem),
        mutationEventId: raw.mutation_event_id,
        mutationType: raw.mutation_type as MutationChangeResult["mutationType"],
    }
}

export async function setGenreChoice(roomCode: string, genre: string): Promise<MutationChangeResult> {
    const res = await postJson(`/room/${roomCode}/genre`, { genre })
    await ensureOk(res, "POSTing new genre")
    return parseMutationResponse(res)
}

export async function setWatchedFilter(
    roomCode: string,
    hideWatched: boolean,
): Promise<MutationChangeResult> {
    const res = await postJson(`/room/${roomCode}/watched-filter`, {
        hide_watched: hideWatched,
    })
    await ensureOk(res, "toggling watched filter")
    return parseMutationResponse(res)
}

// --- Library metadata ---

export async function fetchGenres(): Promise<GenreListResponse> {
    const res = await apiFetch(`/genres`, GET_JSON)
    await ensureOk(res, "fetching genres")
    return res.json()
}

export async function fetchCast(
    mediaId: string,
    signal?: AbortSignal,
): Promise<CastResponse> {
    const res = await apiFetch(`/cast/${mediaId}`, { ...GET_JSON, signal })
    await ensureOk(res, "fetching cast")
    return res.json()
}

export async function fetchMatches(): Promise<MatchItem[]> {
    const res = await apiFetch(`/matches`, GET_JSON)
    await ensureOk(res, "retrieving matches")
    const data: { matches: MatchItemDto[] } = await res.json()
    return data.matches.map(toMatchItem)
}
