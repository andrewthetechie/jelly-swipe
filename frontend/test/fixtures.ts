// Test fixtures — the "object mother" / factory pattern for building Card data.
//
// Why a factory? A `Card` has many fields. If every test hand-built one, the
// tests would be noisy and would break whenever the type changed. Instead,
// `makeCard()` returns a fully-shaped, valid default card, and a test overrides
// only the field it cares about — keeping each test to (almost) one line:
//   makeCard({ season_count: 1 })        // exercise the singular "1 Season"
//   makeCard({ media_type: "tv_show" })  // exercise the "TV" label
//
// SHAPE GOTCHAS (per types.ts — easy to get wrong):
//   - `media_id` is a STRING (not a number)
//   - `duration` is a STRING (e.g. "1h 47m", not minutes)
//   - `season_count` is `number | undefined` — use `undefined`, never `null`
import { fireEvent } from "@testing-library/dom"
import type { CardItem, CardDeck } from "../types"
import type { MatchItem } from "../types"
import type { CastMember } from "../types"

// A complete, sensible default card. Override any field via `overrides`.
export function makeCard(overrides: Partial<CardItem> = {}): CardItem {
  return {
    media_id: "1",
    title: "Moana",
    summary: "A young woman sails beyond the reef.",
    thumb: "/proxy?path=/poster.jpg",
    year: 2016,
    media_type: "movie",
    rating: 7.5,
    duration: "1h 47m",
    season_count: undefined,
    ...overrides,
  }
}

// Build a deck of `n` cards with distinct media_id/title, so tests can assert
// ordering and counts unambiguously (e.g. card-stack slicing in SwipePage).
export function makeDeck(n: number): CardDeck {
  return Array.from({ length: n }, (_, i) =>
    makeCard({ media_id: String(i + 1), title: `Movie ${i + 1}` }),
  )
}

export function makeMatch(overrides: Partial<MatchItem> = {}): MatchItem {
  return {
    media_id: "movie-1",
    media_type: "movie",
    title: "Movie 1",
    thumb: "/poster.jpg",
    deep_link: "https://jellyfin.example.com/web/index.html#!/details?id=movie-1",
    rating: "8.25",
    duration: "107 min",
    year: 2016,
    ...overrides,
  }
}

export function makeCastMember(overrides: Partial<CastMember> = {}): CastMember {
  return {
    name: "Jane Actor",
    character: "Jane Doe",
    profile_path: "https://tmdb.example.com/profile.jpg",
    ...overrides,
  }
}

export function makeCast(n: number, overridesFn?: (i: number) => Partial<CastMember>): CastMember[] {
  return Array.from({ length: n }, (_, i) =>
    makeCastMember(overridesFn?.(i) || { name: `Actor ${i + 1}` }),
  )
}


export async function swipeRight(card: HTMLElement) {
  fireEvent.pointerDown(card, { clientX: 0, pointerId: 1 })
  fireEvent.pointerMove(card, { clientX: 250, pointerId: 1 })
  fireEvent.pointerUp(card, { clientX: 250, pointerId: 1 })
}

export async function swipeLeft(card: HTMLElement) {
  fireEvent.pointerDown(card, { clientX: 0, pointerId: 1 })
  fireEvent.pointerMove(card, { clientX: -250, pointerId: 1 })
  fireEvent.pointerUp(card, { clientX: -250, pointerId: 1 })
}

export async function swipeUnderThreshold(card: HTMLElement) {
  fireEvent.pointerDown(card, { clientX: 0, pointerId: 1 })
  fireEvent.pointerMove(card, { clientX: 10, pointerId: 1 })
  fireEvent.pointerUp(card, { clientX: 10, pointerId: 1 })
}
