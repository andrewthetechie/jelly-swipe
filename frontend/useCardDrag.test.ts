// useCardDrag.test.ts — drives the card drag gesture controller (issue #406,
// first slice) through its outputs with renderHook + synthetic pointer events,
// so the gesture guards (double-fire, live-drag suppression, #342 cancel /
// capture-loss, #345 stamp feedback, #353 drag transition arm) are tested
// directly instead of through a full card mount with stubbed DOM events.
import { act, renderHook } from "@testing-library/react"
import { createRef } from "react"
import type { PointerEvent } from "react"
import { useCardDrag } from "./useCardDrag"

// A minimal stub pointer event: the handlers only read clientX / timeStamp /
// pointerId and the capture methods on currentTarget (no-op stubs installed at
// the harness level in test/setup.ts for real elements; these are plain objects).
function makeEvent(clientX: number, timeStamp = 0, pointerId = 1) {
    return {
        clientX,
        timeStamp,
        pointerId,
        currentTarget: {
            setPointerCapture: vi.fn(),
            releasePointerCapture: vi.fn(),
        },
    } as unknown as PointerEvent<HTMLDivElement>
}

function renderDrag(initialEnabled = true) {
    const ref = createRef<HTMLDivElement>()
    const onVerdict = vi.fn()
    const utils = renderHook(
        ({ enabled }) => useCardDrag(enabled, ref, onVerdict),
        { initialProps: { enabled: initialEnabled } },
    )
    return { ref, onVerdict, ...utils }
}

describe("useCardDrag — swipe behavior", () => {
    it("hands a rightward verdict with direction 1 and the travel distance on a past-threshold release", () => {
        const { result, onVerdict } = renderDrag()
        act(() => result.current.handlePointerDown(makeEvent(0)))
        act(() => result.current.handlePointerMove(makeEvent(250)))
        act(() => result.current.handlePointerUp(makeEvent(250)))

        expect(onVerdict).toHaveBeenCalledTimes(1)
        expect(onVerdict).toHaveBeenCalledWith(1, 0, 250)
    })

    it("hands a leftward verdict with direction -1 and the travel distance", () => {
        const { result, onVerdict } = renderDrag()
        act(() => result.current.handlePointerDown(makeEvent(0)))
        act(() => result.current.handlePointerMove(makeEvent(-250)))
        act(() => result.current.handlePointerUp(makeEvent(-250)))

        expect(onVerdict).toHaveBeenCalledTimes(1)
        expect(onVerdict).toHaveBeenCalledWith(-1, 0, -250)
    })

    it("hands no verdict and snaps back to rest on an under-threshold release", () => {
        const { result, onVerdict } = renderDrag()
        act(() => result.current.handlePointerDown(makeEvent(0)))
        act(() => result.current.handlePointerMove(makeEvent(10)))
        act(() => result.current.handlePointerUp(makeEvent(10)))

        expect(onVerdict).not.toHaveBeenCalled()
        expect(result.current.signal).toBe(0)
        expect(result.current.position).toEqual({ x: 0, y: 0, rotation: 0 })
        expect(result.current.isDragging).toBe(false)
    })
})

describe("useCardDrag — committed guard", () => {
    it("does not double-fire: a second arming attempt returns false", () => {
        const { result } = renderDrag()
        expect(result.current.armCommit()).toBe(true)
        expect(result.current.armCommit()).toBe(false)
    })

    it("snaps back to rest and re-arms when a commit is rejected", () => {
        const { result } = renderDrag()
        expect(result.current.armCommit()).toBe(true)

        // Present the committed state (what the funnel does on a successful commit).
        act(() => {
            result.current.setCommitSignal(1)
            result.current.setCommitPosition({ x: 500, y: 0, rotation: 50 })
        })
        expect(result.current.signal).toBe(1)
        expect(result.current.position).toEqual({ x: 500, y: 0, rotation: 50 })

        // The rejection clears the guard and snaps the card back to rest.
        act(() => {
            result.current.releaseCommitted()
            result.current.setCommitSignal(0)
            result.current.setCommitPosition({ x: 0, y: 0, rotation: 0 })
        })
        expect(result.current.signal).toBe(0)
        expect(result.current.position).toEqual({ x: 0, y: 0, rotation: 0 })

        // The same card can be committed again.
        expect(result.current.armCommit()).toBe(true)
    })

    it("refuses to commit while a drag is live", () => {
        const { result } = renderDrag()
        act(() => result.current.handlePointerDown(makeEvent(0)))
        expect(result.current.isDragActive()).toBe(true)
        expect(result.current.armCommit()).toBe(false)

        // Once the drag ends, the card can be armed again.
        act(() => result.current.handlePointerUp(makeEvent(0)))
        expect(result.current.isDragActive()).toBe(false)
        expect(result.current.armCommit()).toBe(true)
    })
})

describe("useCardDrag — interrupted drag (issue #342)", () => {
    it("resets cleanly on pointercancel mid-drag", () => {
        const { result, onVerdict } = renderDrag()
        act(() => result.current.handlePointerDown(makeEvent(0)))
        act(() => result.current.handlePointerMove(makeEvent(250)))
        act(() => result.current.handlePointerCancel())

        expect(onVerdict).not.toHaveBeenCalled()
        expect(result.current.signal).toBe(0)
        expect(result.current.position).toEqual({ x: 0, y: 0, rotation: 0 })
        expect(result.current.isDragging).toBe(false)
    })

    it("resets cleanly when pointer capture is lost mid-drag", () => {
        const { result, onVerdict } = renderDrag()
        act(() => result.current.handlePointerDown(makeEvent(0)))
        act(() => result.current.handlePointerMove(makeEvent(250)))
        act(() => result.current.handleLostPointerCapture())

        expect(onVerdict).not.toHaveBeenCalled()
        expect(result.current.signal).toBe(0)
        expect(result.current.position).toEqual({ x: 0, y: 0, rotation: 0 })
        expect(result.current.isDragging).toBe(false)
    })

    it("leaves a committed card untouched when capture is lost after a normal release", () => {
        const { result, onVerdict } = renderDrag()
        act(() => result.current.handlePointerDown(makeEvent(0)))
        act(() => result.current.handlePointerMove(makeEvent(250)))
        // The component's funnel would present the committed stamp/transform.
        act(() => {
            result.current.setCommitSignal(1)
            result.current.setCommitPosition({ x: 500, y: 0, rotation: 50 })
        })
        act(() => result.current.handlePointerUp(makeEvent(250)))
        expect(onVerdict).toHaveBeenCalledTimes(1)

        // A late lostpointercapture (or a stray pointercancel) must not reset
        // the armed/committed state or the commit-presented position.
        act(() => result.current.handleLostPointerCapture())
        act(() => result.current.handlePointerCancel())
        expect(result.current.position).toEqual({ x: 500, y: 0, rotation: 50 })
        expect(result.current.signal).toBe(1)
    })
})

describe("useCardDrag — swipe verdict feedback (issue #345)", () => {
    it("keeps signal at 0 inside the dead zone", () => {
        const { result } = renderDrag()
        act(() => result.current.handlePointerDown(makeEvent(0)))
        act(() => result.current.handlePointerMove(makeEvent(10)))
        expect(result.current.signal).toBe(0)
    })

    it("lights LIKE (positive signal) on a rightward drag", () => {
        const { result } = renderDrag()
        act(() => result.current.handlePointerDown(makeEvent(0)))
        act(() => result.current.handlePointerMove(makeEvent(50)))
        expect(result.current.signal).toBeGreaterThan(0)
    })

    it("lights NOPE (negative signal) on a leftward drag", () => {
        const { result } = renderDrag()
        act(() => result.current.handlePointerDown(makeEvent(0)))
        act(() => result.current.handlePointerMove(makeEvent(-50)))
        expect(result.current.signal).toBeLessThan(0)
    })

    it("saturates signal at ±1 past the threshold", () => {
        const { result } = renderDrag()
        act(() => result.current.handlePointerDown(makeEvent(0)))
        act(() => result.current.handlePointerMove(makeEvent(250)))
        expect(result.current.signal).toBe(1)
    })
})

describe("useCardDrag — drag transition arm (issue #353)", () => {
    it("flips isDragging true on pointerdown and back to false on release", () => {
        const { result } = renderDrag()
        expect(result.current.isDragging).toBe(false)
        act(() => result.current.handlePointerDown(makeEvent(0)))
        expect(result.current.isDragging).toBe(true)
        act(() => result.current.handlePointerUp(makeEvent(0)))
        expect(result.current.isDragging).toBe(false)
    })

    it("flips isDragging back to false on cancel", () => {
        const { result } = renderDrag()
        act(() => result.current.handlePointerDown(makeEvent(0)))
        expect(result.current.isDragging).toBe(true)
        act(() => result.current.handlePointerCancel())
        expect(result.current.isDragging).toBe(false)
    })
})

describe("useCardDrag — hasDragged guard", () => {
    it("sets hasDragged after a >5px travel and resets it on a new gesture", () => {
        const { result } = renderDrag()
        expect(result.current.hasDragged()).toBe(false)
        act(() => result.current.handlePointerDown(makeEvent(0)))
        act(() => result.current.handlePointerMove(makeEvent(50)))
        expect(result.current.hasDragged()).toBe(true)
        // A new gesture resets it.
        act(() => result.current.handlePointerDown(makeEvent(0)))
        expect(result.current.hasDragged()).toBe(false)
    })
})

describe("useCardDrag — enabled flag", () => {
    it("is inert when disabled — gesture state untouched", () => {
        const { result, onVerdict } = renderDrag(false)
        act(() => result.current.handlePointerDown(makeEvent(0)))
        act(() => result.current.handlePointerMove(makeEvent(250)))
        act(() => result.current.handlePointerUp(makeEvent(250)))
        act(() => result.current.handlePointerCancel())
        act(() => result.current.handleLostPointerCapture())

        expect(result.current.isDragging).toBe(false)
        expect(result.current.signal).toBe(0)
        expect(result.current.position).toEqual({ x: 0, y: 0, rotation: 0 })
        expect(result.current.isDragActive()).toBe(false)
        expect(result.current.hasDragged()).toBe(false)
        expect(onVerdict).not.toHaveBeenCalled()
    })
})
