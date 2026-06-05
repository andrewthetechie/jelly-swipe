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