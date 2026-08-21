import { describe, expect, it } from "vitest"
import { apiUrl } from "./api"
import { toCardItem, toMatchItem } from "./mediaAdapter"

describe("toCardItem", () => {
    it("converts snake_case fields to camelCase", () => {
        const card = toCardItem({
            media_id: "1",
            title: "Moana",
            media_type: "movie",
            season_count: 2,
        })
        expect(card.mediaId).toBe("1")
        expect(card.mediaType).toBe("movie")
        expect(card.seasonCount).toBe(2)
    })

    it("resolves a relative thumb to an absolute posterUrl", () => {
        const card = toCardItem({ media_id: "1", title: "Moana", thumb: "/Items/1/Images/Primary" })
        expect(card.posterUrl).toBe(apiUrl("/Items/1/Images/Primary").toString())
    })

    it.each([undefined, null, ""])("maps thumb %s to a null posterUrl", (thumb) => {
        const card = toCardItem({ media_id: "1", title: "Moana", thumb })
        expect(card.posterUrl).toBeNull()
    })
})

describe("toMatchItem", () => {
    it("converts a full /matches payload", () => {
        const match = toMatchItem({
            media_id: "1",
            media_type: "movie",
            title: "Moana",
            thumb: "/poster.jpg",
            deep_link: "https://jellyfin.example.com/details?id=1",
            rating: 7.5,
            duration: "1h 47m",
            year: 2016,
        })
        expect(match).toEqual({
            mediaId: "1",
            mediaType: "movie",
            title: "Moana",
            posterUrl: apiUrl("/poster.jpg").toString(),
            deepLink: "https://jellyfin.example.com/details?id=1",
            rating: 7.5,
            duration: "1h 47m",
            year: 2016,
        })
    })

    it("fills absent fields with null (sparse SSE match_found event)", () => {
        expect(toMatchItem({})).toEqual({
            title: null,
            posterUrl: null,
            mediaId: null,
            mediaType: null,
            deepLink: null,
            rating: null,
            duration: null,
            year: null,
        })
    })
})