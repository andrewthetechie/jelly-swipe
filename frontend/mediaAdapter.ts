import { apiUrl } from "./api"
import type { CardItem, MatchItem } from "./types"

export interface CardItemDto {
    media_id: string
    title: string
    summary?: string
    thumb?: string | null
    year?: number | null
    media_type?: string
    rating?: number | null
    duration?: string | null
    season_count?: number | null
}

export interface MatchItemDto {
    title?: string | null
    thumb?: string | null
    media_id?: string | null
    media_type?: string | null
    deep_link?: string | null
    rating?: number | null
    duration?: string | null
    year?: number | null
}

function toAbsolutePosterUrl(thumb: string | null | undefined): string | null {
    return thumb ? apiUrl(thumb).toString() : null
}

export function toCardItem(dto: CardItemDto): CardItem {
    return {
        mediaId: dto.media_id,
        title: dto.title,
        summary: dto.summary,
        posterUrl: toAbsolutePosterUrl(dto.thumb),
        year: dto.year,
        mediaType: dto.media_type,
        rating: dto.rating,
        duration: dto.duration,
        seasonCount: dto.season_count,
    }
}

export function toMatchItem(dto: MatchItemDto): MatchItem {
    return {
        title: dto.title ?? null,
        posterUrl: toAbsolutePosterUrl(dto.thumb),
        mediaId: dto.media_id ?? null,
        mediaType: dto.media_type ?? null,
        deepLink: dto.deep_link ?? null,
        rating: dto.rating ?? null,
        duration: dto.duration ?? null,
        year: dto.year ?? null,
    }
}