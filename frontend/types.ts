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

export interface SessionBootstrapResponse {
    event_type: string,
    instance_id: string
    ready: boolean,
    genre: string,
    solo: boolean,
    hide_watched: boolean,
    replay_boundary: number
}

export interface SwipeRequest {
    media_id: string,
    direction: string | null
}