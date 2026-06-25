export interface CardItem {
    media_id: string,
    title: string,
    summary?: string,
    thumb?: string,
    year?: number | null,
    media_type?: string,
    rating?: number | null,
    duration?: string | null,
    season_count?: number | null
}

export type CardDeck = CardItem[]

export interface RoomStatusResponse {
    ready: boolean
    genre?: string | null
    solo?: boolean | null
    hide_watched?: boolean | null
}

export interface SwipeRequest {
    media_id: string,
    direction: string | null
}

interface BaseSSEEvent {
    event_type: string
}

interface LedgerEvent extends BaseSSEEvent {
    event_id: number
}

export interface SessionBootstrapResponse extends BaseSSEEvent {
    event_type: string,
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
    title: string
    thumb?: string
    media_type?: string
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