export interface Card {
    media_id: string,
    title: string,
    summary?: string,
    thumb?: string,
    year?: number,
    media_type?: string,
    rating?: number,
    duration?: string,
    season_count?: number | undefined
}

export type CardDeck = Card[]