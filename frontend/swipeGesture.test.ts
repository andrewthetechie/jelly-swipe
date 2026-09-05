import { describe, expect, it } from "vitest"
import {
    computeVelocity,
    exitDistanceFor,
    shouldCommitSwipe,
    stampSignal,
    swipeThresholdFor,
    trackSample,
    MIN_FLICK_DISTANCE_PX,
    STAMP_DEAD_ZONE_PX,
    SWIPE_THRESHOLD_RATIO,
    MIN_SWIPE_THRESHOLD_PX,
    MAX_EXIT_DISTANCE_PX,
    VELOCITY_WINDOW_MS,
    type PointerSample,
} from "./swipeGesture"

describe("computeVelocity", () => {
    it("returns 0 with fewer than 2 samples", () => {
        expect(computeVelocity([])).toBe(0)
        expect(computeVelocity([{ x: 100, time: 50 }])).toBe(0)
    })

    it("returns 0 when the window spans less than MIN_SAMPLE_DT_MS (the jsdom guard)", () => {
        // jsdom fires synthetic events sub-millisecond apart; without this
        // guard, dividing by ~0 would report an enormous flick on every test.
        expect(computeVelocity([
            { x: 0, time: 100 },
            { x: 100, time: 100.5 },
        ])).toBe(0)
    })

    it("computes a rightward velocity in px/ms", () => {
        expect(computeVelocity([
            { x: 0, time: 0 },
            { x: 100, time: 100 },
        ])).toBe(1)
    })

    it("reports a leftward drag as negative", () => {
        expect(computeVelocity([
            { x: 100, time: 0 },
            { x: 0, time: 100 },
        ])).toBe(-1)
    })

    it("uses only the first and last samples across the window", () => {
        // Interim samples don't affect the endpoint-based estimate.
        expect(computeVelocity([
            { x: 0, time: 0 },
            { x: 500, time: 50 },
            { x: 100, time: 100 },
        ])).toBe(1)
    })
})

describe("trackSample", () => {
    it("drops samples older than VELOCITY_WINDOW_MS relative to the newest", () => {
        const initial: PointerSample[] = [
            { x: 0, time: 0 },
            { x: 50, time: 80 },
        ]
        const next = trackSample(initial, { x: 100, time: 120 })
        // 120 - 0 = 120 > 100 → drop; 120 - 80 = 40 → keep; new sample kept.
        expect(next).toHaveLength(2)
        expect(next[0]).toEqual({ x: 50, time: 80 })
        expect(next[1]).toEqual({ x: 100, time: 120 })
    })

    it("keeps at least 2 entries even when every older sample is outside the window", () => {
        const initial: PointerSample[] = [
            { x: 0, time: 0 },
            { x: 50, time: 10 },
        ]
        const next = trackSample(initial, { x: 100, time: 500 })
        // 500 - 0, 500 - 10 both exceed VELOCITY_WINDOW_MS → only the new
        // one would survive the filter; the fallback keeps the last two.
        expect(next).toHaveLength(2)
        expect(next[1]).toEqual({ x: 100, time: 500 })
        expect(next[0]).toEqual({ x: 50, time: 10 })
    })

    it("appends a first sample when the list is empty", () => {
        expect(trackSample([], { x: 42, time: 7 })).toEqual([{ x: 42, time: 7 }])
    })

    it("window is exactly the constant", () => {
        // Sanity check that the constants match the module — a drift here
        // would silently break the drop rule above.
        expect(VELOCITY_WINDOW_MS).toBeGreaterThan(0)
    })
})

describe("swipeThresholdFor", () => {
    it("scales with a 400px desktop card (~112)", () => {
        // 400 * 0.28 = 112.00000000000001 in IEEE 754 — toBeCloseTo, not toBe.
        expect(swipeThresholdFor(400)).toBeCloseTo(112)
    })

    it("falls back to a 320px width when measured 0 (~89.6)", () => {
        expect(swipeThresholdFor(0)).toBeCloseTo(89.6)
    })

    it("floors narrow cards at MIN_SWIPE_THRESHOLD_PX", () => {
        // 100 * 0.28 = 28 < 60, so the floor applies; 60 is an exact integer.
        expect(swipeThresholdFor(100)).toBe(MIN_SWIPE_THRESHOLD_PX)
    })

    it("matches the ratio formula for a mid-range width", () => {
        // 320 * 0.28 = 89.60000000000001.
        expect(swipeThresholdFor(320)).toBeCloseTo(320 * SWIPE_THRESHOLD_RATIO)
    })
})

describe("shouldCommitSwipe", () => {
    const threshold = 100

    it("commits on distance alone at zero velocity", () => {
        expect(shouldCommitSwipe(150, 0, threshold)).toBe(true)
        expect(shouldCommitSwipe(-150, 0, threshold)).toBe(true)
    })

    it("commits exactly at the threshold distance", () => {
        expect(shouldCommitSwipe(100, 0, threshold)).toBe(true)
    })

    it("commits on a 40px+ same-sign flick even short of the threshold", () => {
        // distance 60, velocity 0.6 px/ms → flick arm triggers.
        expect(shouldCommitSwipe(60, 0.6, threshold)).toBe(true)
        expect(shouldCommitSwipe(-60, -0.6, threshold)).toBe(true)
    })

    it("does NOT commit on a short flick below MIN_FLICK_DISTANCE_PX", () => {
        // 30 < 40 → jitter guard rejects even a fast velocity.
        expect(shouldCommitSwipe(30, 0.9, threshold)).toBe(false)
    })

    it("does NOT commit when the flick opposes the drag direction", () => {
        // Snatching right→left must never commit a right swipe (and vice-versa).
        expect(shouldCommitSwipe(60, -0.9, threshold)).toBe(false)
        expect(shouldCommitSwipe(-60, 0.9, threshold)).toBe(false)
    })

    it("does NOT commit on a slow short drag", () => {
        expect(shouldCommitSwipe(30, 0.1, threshold)).toBe(false)
    })

    it("respects MIN_FLICK_DISTANCE_PX boundary exactly at the minimum", () => {
        expect(MIN_FLICK_DISTANCE_PX).toBe(40)
        expect(shouldCommitSwipe(MIN_FLICK_DISTANCE_PX, 0.5, threshold)).toBe(true)
    })
})

describe("exitDistanceFor", () => {
    it("returns viewport/2 + card width at zero velocity (jsdom case: 832)", () => {
        // Clearance is the only term; integer-valued so toBe is fine.
        expect(exitDistanceFor(0, 320, 1024)).toBe(832)
    })

    it("grows with release velocity", () => {
        const slow = exitDistanceFor(0.2, 320, 1024)
        const fast = exitDistanceFor(1.0, 320, 1024)
        expect(fast).toBeGreaterThan(slow)
    })

    it("clamps at MAX_EXIT_DISTANCE_PX on a violent flick", () => {
        expect(exitDistanceFor(20, 400, 1920)).toBe(MAX_EXIT_DISTANCE_PX)
    })

    it("always covers viewport/2 + card width", () => {
        // No matter how gentle, the card at least clears the viewport centre.
        expect(exitDistanceFor(0, 200, 800)).toBe(600) // 800/2 + 200
    })

    it("uses fallback width when viewport reports 0", () => {
        // viewport 0 → fall back to 320, card 320 → clearance 480 + boost
        expect(exitDistanceFor(0, 320, 0)).toBe(480)
    })
})

describe("stampSignal", () => {
    const threshold = 100

    it("returns 0 when the pointer hasn't moved", () => {
        expect(stampSignal(0, 0, threshold)).toBe(0)
    })

    it("returns 0 inside the dead zone", () => {
        expect(stampSignal(STAMP_DEAD_ZONE_PX, 0, threshold)).toBe(0)
        expect(stampSignal(-STAMP_DEAD_ZONE_PX, 0, threshold)).toBe(0)
    })

    it("ramps between the dead zone and the threshold", () => {
        // 56 is past the dead zone (12) but short of the threshold (100).
        // (56 - 12) / (100 - 12) = 44 / 88 = 0.5 exactly.
        expect(stampSignal(56, 0, threshold)).toBe(0.5)
    })

    it("is negative for leftward drags", () => {
        expect(stampSignal(-56, 0, threshold)).toBe(-0.5)
    })

    it("clamps at +1 at the threshold", () => {
        expect(stampSignal(100, 0, threshold)).toBe(1)
    })

    it("clamps at -1 at the negative threshold", () => {
        expect(stampSignal(-100, 0, threshold)).toBe(-1)
    })

    it("saturates to +1 on a fast flick well short of the threshold (#345 rule)", () => {
        // distance 50 (well under 100), velocity 0.6 same sign — a flick
        // commit. The stamp must warn the user NOW, not at 100px.
        expect(stampSignal(50, 0.6, threshold)).toBe(1)
    })

    it("saturates to -1 on a fast leftward flick", () => {
        expect(stampSignal(-50, -0.6, threshold)).toBe(-1)
    })

    it("does NOT saturate when the flick opposes the drag", () => {
        // distance 50 rightward, velocity -0.9 leftward → no commit, ramp only.
        const v = stampSignal(50, -0.9, threshold)
        expect(v).toBeGreaterThan(0)
        expect(v).toBeLessThan(1)
    })
})
