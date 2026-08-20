import { describe, expect, it } from "vitest"
import { formatRating } from "./format"

describe("formatRating", () => {
    it("formats an integer to two decimal places", () => {
        expect(formatRating(8)).toBe("8.00")
    })

    it("rounds to two decimal places", () => {
        expect(formatRating(7.556)).toBe("7.56")
        expect(formatRating(7.554)).toBe("7.55")
    })

    it("preserves a value already at two decimal places", () => {
        expect(formatRating(6.75)).toBe("6.75")
    })

    it("handles zero", () => {
        expect(formatRating(0)).toBe("0.00")
    })

    it("handles negative values", () => {
        expect(formatRating(-1.5)).toBe("-1.50")
    })
})
