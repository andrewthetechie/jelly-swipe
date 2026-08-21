export interface CardItem {
    mediaId: string,
    title: string,
    summary?: string,
    posterUrl?: string | null,
    year?: number | null,
    mediaType?: string,
    rating?: number | null,
    duration?: string | null,
    seasonCount?: number | null
}

export interface MatchItem {
    title: string | null
    posterUrl: string | null
    mediaId: string | null
    mediaType: string | null
    deepLink: string | null
    rating: number | null
    duration: string | null
    year: number | null
}

export type CardDeck = CardItem[]

export interface CastMember {
    name: string
    character: string
    profile_path?: string | null
}

export interface CastResponse {
    cast: CastMember[]
}

export type GenreListResponse = string[]

export interface RoomStatusResponse {
    ready: boolean
    genre?: string | null
    solo?: boolean | null
    hide_watched?: boolean | null
}

interface BaseSSEEvent {
    event_type: string
}

interface LedgerEvent extends BaseSSEEvent {
    event_id: number
}

export interface SessionBootstrapResponse extends BaseSSEEvent {
    event_type: "session_bootstrap",
    instance_id: string
    ready: boolean,
    genre: string,
    solo: boolean,
    hide_watched: boolean,
    replay_boundary: number
}


export interface SessionReadyEvent extends LedgerEvent {
    event_type: "session_ready"
    genre?: string
    solo?: boolean
}

export interface MatchFoundEvent extends LedgerEvent {
    event_type: "match_found"
    title?: string | null
    thumb?: string | null
    media_id?: string | null
    media_type?: string | null
    deep_link?: string | null
    duration?: string | null
    rating?: number | null
    year?: number | null
}

export interface GenreChangedEvent extends LedgerEvent {
    event_type: "genre_changed"
    genre?: string
}

export interface HideWatchedChangedEvent extends LedgerEvent {
    event_type: "hide_watched_changed"
    hide_watched?: boolean
}

export interface SessionClosedEvent extends LedgerEvent {
    event_type: "session_closed"
}

export interface SessionResetEvent extends BaseSSEEvent {
    event_type: "session_reset"
}

export type SSEEvent =
    | SessionBootstrapResponse
    | SessionReadyEvent
    | MatchFoundEvent
    | GenreChangedEvent
    | HideWatchedChangedEvent
    | SessionClosedEvent
    | SessionResetEvent
