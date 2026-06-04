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
import type { Card, CardDeck } from "../types";

// A complete, sensible default card. Override any field via `overrides`.
export function makeCard(overrides: Partial<Card> = {}): Card {
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
  };
}

// Build a deck of `n` cards with distinct media_id/title, so tests can assert
// ordering and counts unambiguously (e.g. card-stack slicing in SwipePage).
export function makeDeck(n: number): CardDeck {
  return Array.from({ length: n }, (_, i) =>
    makeCard({ media_id: String(i + 1), title: `Movie ${i + 1}` }),
  );
}
