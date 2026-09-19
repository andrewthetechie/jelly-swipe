// useLeavingCards.test.ts — covers the SwipePage "leaving card" hook (issue
// #360): array semantics, per-entry timers, reduced-motion hold, and the
// undo-head clearing that drops a leaving entry when its card is restored.
//
// The deck passed to the hook models the CURRENT deck: by the time a leaving
// entry is recorded, the committed card has already been sliced off the head
// (SWIPE_SUCCEEDED slices the deck before SwipePage records the leaving entry),
// so committed cards here always differ from the deck head unless an undo has
// restored one.
import { act, renderHook } from "@testing-library/react"
import { useLeavingCards } from "./useLeavingCards"
import { makeCard, makeDeck } from "./test/fixtures"

/** Stub `window.matchMedia` to a fixed `matches` value (the setup.ts stub
 * defaults to `matches: false`; tests flip it for reduced motion). */
function stubMatchMedia(matches: boolean) {
  const mql = {
    matches,
    media: "(prefers-reduced-motion: reduce)",
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
    onchange: null,
  }
  vi.stubGlobal("matchMedia", vi.fn(() => mql))
}

// A deck whose head is NOT the card being committed, modelling the post-slice
// deck (head "2", committed cards are "1"/"2"/…).
const postSliceDeck = makeDeck(3).slice(1) // [2, 3]

describe("useLeavingCards", () => {
  beforeEach(() => {
    vi.useFakeTimers()
    stubMatchMedia(false)
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it("records a leaving entry on commit", () => {
    const { result } = renderHook(() => useLeavingCards(postSliceDeck))

    act(() => result.current.commit(makeCard({ mediaId: "1" }), "right"))

    expect(result.current.leavingCards).toHaveLength(1)
    expect(result.current.leavingCards[0].card.mediaId).toBe("1")
    expect(result.current.leavingCards[0].direction).toBe("right")
    expect(result.current.leavingCards[0].key).toMatch(/^leaving-1-\d+$/)
  })

  it("stores the committed transform on the entry when one is threaded", () => {
    const { result } = renderHook(() => useLeavingCards(postSliceDeck))

    act(() =>
      result.current.commit(makeCard({ mediaId: "1" }), "right", {
        x: 832,
        y: 0,
        rotation: 50,
      }),
    )

    expect(result.current.leavingCards[0].from).toEqual({ x: 832, y: 0, rotation: 50 })
  })

  it("self-removes the entry after the hold duration", () => {
    const { result } = renderHook(() => useLeavingCards(postSliceDeck))

    act(() => result.current.commit(makeCard({ mediaId: "1" }), "right"))
    expect(result.current.leavingCards).toHaveLength(1)

    // Just before the 400ms hold ends, the entry is still present…
    act(() => vi.advanceTimersByTime(399))
    expect(result.current.leavingCards).toHaveLength(1)

    // …and is removed once the hold elapses.
    act(() => vi.advanceTimersByTime(1))
    expect(result.current.leavingCards).toHaveLength(0)
  })

  it("uses a 150ms hold under prefers-reduced-motion", () => {
    stubMatchMedia(true)
    const { result } = renderHook(() => useLeavingCards(postSliceDeck))

    act(() => result.current.commit(makeCard({ mediaId: "1" }), "left"))
    expect(result.current.leavingCards).toHaveLength(1)

    act(() => vi.advanceTimersByTime(149))
    expect(result.current.leavingCards).toHaveLength(1)

    act(() => vi.advanceTimersByTime(1))
    expect(result.current.leavingCards).toHaveLength(0)
  })

  it("keys each commit uniquely, even for the same card", () => {
    const { result } = renderHook(() => useLeavingCards(postSliceDeck))

    act(() => result.current.commit(makeCard({ mediaId: "1" }), "right"))
    act(() => result.current.commit(makeCard({ mediaId: "1" }), "left"))

    expect(result.current.leavingCards).toHaveLength(2)
    const keys = result.current.leavingCards.map((entry) => entry.key)
    expect(new Set(keys).size).toBe(2)
  })

  it("gives each entry its own timer", () => {
    const { result } = renderHook(() => useLeavingCards(makeDeck(3).slice(2))) // head "3"

    act(() => result.current.commit(makeCard({ mediaId: "1" }), "right"))
    act(() => vi.advanceTimersByTime(200))
    act(() => result.current.commit(makeCard({ mediaId: "2" }), "left"))

    // The first entry's 400ms hold expires after 200 more ms; the second entry
    // was committed 200ms later, so it still has 200ms left.
    act(() => vi.advanceTimersByTime(200))
    expect(result.current.leavingCards).toHaveLength(1)
    expect(result.current.leavingCards[0].card.mediaId).toBe("2")

    act(() => vi.advanceTimersByTime(200))
    expect(result.current.leavingCards).toHaveLength(0)
  })

  it("keeps a leaving entry when a normal swipe changes the deck head", () => {
    // Deck head is "2" (post-swipe of card 1); commit card 1, then a normal
    // swipe moves the head to "3" — neither matches card 1, so the entry stays.
    const { result, rerender } = renderHook(
      ({ deck }) => useLeavingCards(deck),
      { initialProps: { deck: makeDeck(3).slice(1) } }, // head "2"
    )

    act(() => result.current.commit(makeCard({ mediaId: "1" }), "right"))
    expect(result.current.leavingCards).toHaveLength(1)

    rerender({ deck: makeDeck(3).slice(2) }) // head "3"
    expect(result.current.leavingCards).toHaveLength(1)
  })

  it("drops a leaving entry when an undo restores that card to the deck head", () => {
    const { result, rerender } = renderHook(
      ({ deck }) => useLeavingCards(deck),
      { initialProps: { deck: makeDeck(3).slice(1) } }, // head "2"
    )

    // Swipe card 1 → leaving entry; deck head is 2.
    act(() => result.current.commit(makeCard({ mediaId: "1" }), "right"))
    expect(result.current.leavingCards).toHaveLength(1)

    // Undo restores card 1 to the head → its leaving entry is dropped.
    rerender({ deck: makeDeck(3) }) // head "1"
    expect(result.current.leavingCards).toHaveLength(0)
  })

  it("clears all entry timers on unmount", () => {
    const { result, unmount } = renderHook(() => useLeavingCards(makeDeck(3).slice(2))) // head "3"

    act(() => result.current.commit(makeCard({ mediaId: "1" }), "right"))
    act(() => result.current.commit(makeCard({ mediaId: "2" }), "left"))
    expect(vi.getTimerCount()).toBe(2)

    unmount()
    expect(vi.getTimerCount()).toBe(0)
  })
})
