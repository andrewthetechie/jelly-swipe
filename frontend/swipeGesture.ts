// swipeGesture.ts — pure gesture maths for the card drag (issues #342, #345)
// and the shared commit fly-off target (issue #360).
//
// Deliberately free of React and the DOM. jsdom implements neither PointerEvent
// nor the Pointer Capture API, so a real drag can only ever be stubbed in the
// component tests (see the documented drag stub in CardItemView.test.tsx). Every
// decision the gesture makes therefore lives here, where it can be unit-tested
// directly against numbers.

export type PointerSample = {
    /** clientX of the pointer at this moment. */
    x: number
    /** Event timestamp in milliseconds (React's `event.timeStamp`). */
    time: number
}

/** A card's placement: translate plus rotation (CardItemView's position state). */
export type Position = {
    x: number,
    y: number,
    rotation: number
}

/** Only samples from the last this-many ms feed the velocity estimate. */
export const VELOCITY_WINDOW_MS = 100

/**
 * Velocity needs a real time gap to mean anything. jsdom fires synthetic events
 * sub-millisecond apart, which would otherwise divide by ~0 and report an
 * enormous flick on every test drag.
 */
export const MIN_SAMPLE_DT_MS = 1

/** A release this fast commits the swipe regardless of distance travelled. */
export const FLICK_VELOCITY_PX_PER_MS = 0.5

/** ...but never from a jitter: a flick must still have travelled this far. */
export const MIN_FLICK_DISTANCE_PX = 40

/** Distance threshold as a fraction of the card's own width (issue #342). */
export const SWIPE_THRESHOLD_RATIO = 0.28

/** Floor for the distance threshold, for very narrow cards. */
export const MIN_SWIPE_THRESHOLD_PX = 60

/** Stand-in width when the card has not been measured yet (jsdom, first paint). */
export const FALLBACK_CARD_WIDTH_PX = 320

/** Travel below this shows no stamp at all, so a tap never flashes one. */
export const STAMP_DEAD_ZONE_PX = 12

/** Extra fly-off distance per px/ms of release velocity. */
export const EXIT_VELOCITY_BOOST_PX = 250

/** Hard cap so a violent flick can't produce an absurd transform. */
export const MAX_EXIT_DISTANCE_PX = 2000

/**
 * Rotation (degrees) applied to a commit with no drag travel — the imperative
 * button/keyboard commit and the leaving card's continued exit — so every exit
 * path shares one direction-signed constant (issue #360).
 */
export const COMMIT_ROTATION_DEG = 12

/**
 * How long a committed card's fly-off exit transition runs, and therefore how
 * long SwipePage keeps its leaving card mounted (issue #360). Both the inline
 * exit transition in CardItemView and the unmount hold in useLeavingCards are
 * derived from this pair, so the animation and the hold cannot drift apart.
 * 400ms normally, 150ms under `prefers-reduced-motion: reduce`.
 */
export const EXIT_TRANSITION_MS = 400
export const REDUCED_MOTION_EXIT_TRANSITION_MS = 150

/** Append a sample, dropping any that have aged out of the velocity window. */
export function trackSample(
    samples: PointerSample[],
    sample: PointerSample,
): PointerSample[] {
    const next: PointerSample[] = [...samples, sample]
    const fresh: PointerSample[] = next.filter(
        (s: PointerSample) => sample.time - s.time <= VELOCITY_WINDOW_MS,
    )
    // Always keep enough history to compute a velocity at all.
    return fresh.length >= 2 ? fresh : next.slice(-2)
}

/** Signed px/ms across the sample window. Positive is a rightward drag. */
export function computeVelocity(samples: PointerSample[]): number {
    if (samples.length < 2) return 0
    const first: PointerSample = samples[0]
    const last: PointerSample = samples[samples.length - 1]
    const dt: number = last.time - first.time
    if (dt < MIN_SAMPLE_DT_MS) return 0
    return (last.x - first.x) / dt
}

/**
 * The distance a slow drag must cover to commit, as a fraction of the card's
 * width — so the gesture means the same thing on a 320px phone and a 400px
 * desktop card (issue #342).
 */
export function swipeThresholdFor(cardWidth: number): number {
    const width: number = cardWidth > 0 ? cardWidth : FALLBACK_CARD_WIDTH_PX
    return Math.max(width * SWIPE_THRESHOLD_RATIO, MIN_SWIPE_THRESHOLD_PX)
}

/**
 * Commit on distance OR on a flick. The flick arm requires a minimum travel and
 * that the flick goes the same way the card was already dragged, so that
 * dragging right and then snatching back left never commits a right swipe.
 */
export function shouldCommitSwipe(
    distance: number,
    velocity: number,
    threshold: number,
): boolean {
    if (Math.abs(distance) >= threshold) return true
    return (
        Math.abs(velocity) >= FLICK_VELOCITY_PX_PER_MS &&
        Math.abs(distance) >= MIN_FLICK_DISTANCE_PX &&
        Math.sign(velocity) === Math.sign(distance)
    )
}

/**
 * How far the committed card is thrown, as a positive magnitude — enough to
 * clear the viewport from centre, plus a boost for how hard it was flicked
 * (issue #342, replacing the old hardcoded 1000).
 */
export function exitDistanceFor(
    velocity: number,
    cardWidth: number,
    viewportWidth: number,
): number {
    const width: number = cardWidth > 0 ? cardWidth : FALLBACK_CARD_WIDTH_PX
    const view: number = viewportWidth > 0 ? viewportWidth : FALLBACK_CARD_WIDTH_PX
    const clearance: number = view / 2 + width
    return Math.min(
        clearance + Math.abs(velocity) * EXIT_VELOCITY_BOOST_PX,
        MAX_EXIT_DISTANCE_PX,
    )
}

/**
 * The transform a committed card flies off with (issue #360) — the single
 * definition shared by the commit path (CardItemView.commitSwipe) and the
 * leaving card's exit mount effect, so the leaving card continues the same
 * fly-off instead of a hand-copied formula drifting from it. `velocity` and
 * `dragDistance` are the commit's release velocity and signed travel; the
 * velocity-0/drag-0 call is the target a leaving card continues toward.
 */
export function flyOffTarget(
    direction: 1 | -1,
    velocity: number,
    dragDistance: number,
    cardWidth: number,
    viewportWidth: number,
): Position {
    return {
        x: direction * exitDistanceFor(velocity, cardWidth, viewportWidth),
        y: 0,
        // The drag path rotates by dragDistance / 5 of the live travel; an
        // imperative button/key commit has no drag distance, so use a small
        // direction-signed constant.
        rotation: dragDistance !== 0 ? dragDistance / 5 : direction * COMMIT_ROTATION_DEG,
    }
}

/**
 * Parse a computed transform string back into a Position for the leaving-card
 * capture (issue #360). Real browsers report `matrix(a, b, c, d, e, f)` with
 * x = e, y = f and rotation = atan2(b, a) in degrees; jsdom echoes the inline
 * `translate(px, px) rotate(deg)` form verbatim because it does not run CSS
 * transforms. Both describe the same physical state, so the capture reads either.
 */
export function parseComputedTransform(transform: string): Position {
    const matrix = transform.match(/matrix\(([^)]+)\)/)
    if (matrix) {
        const [a, b, , , e, f] = matrix[1].split(",").map((v) => parseFloat(v))
        return {
            x: e,
            y: f,
            rotation: Math.atan2(b, a) * 180 / Math.PI,
        }
    }
    const tx = transform.match(/translate\((-?[\d.]+)px/)
    const ty = transform.match(/,\s*(-?[\d.]+)px\)/)
    const rot = transform.match(/rotate\((-?[\d.]+)deg\)/)
    return {
        x: tx ? parseFloat(tx[1]) : 0,
        y: ty ? parseFloat(ty[1]) : 0,
        rotation: rot ? parseFloat(rot[1]) : 0,
    }
}

/**
 * Signed stamp strength in [-1, 1]: positive lights LIKE, negative lights NOPE,
 * magnitude is the opacity. It saturates at ±1 the moment the gesture would
 * actually commit — including on a fast flick the card hasn't travelled far on —
 * so a full-strength stamp always means "let go now and this commits" (#345).
 */
export function stampSignal(
    distance: number,
    velocity: number,
    threshold: number,
): number {
    if (distance === 0) return 0
    const direction: number = distance > 0 ? 1 : -1
    if (shouldCommitSwipe(distance, velocity, threshold)) return direction
    const travelled: number = Math.abs(distance)
    if (travelled <= STAMP_DEAD_ZONE_PX) return 0
    const span: number = Math.max(threshold - STAMP_DEAD_ZONE_PX, 1)
    return direction * Math.min((travelled - STAMP_DEAD_ZONE_PX) / span, 1)
}
