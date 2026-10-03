// useSwipeDeckKeyboard.test.ts — covers the deck keyboard controller hook
// (issue #419): the key-to-action map, interactive-focus guard, key-repeat
// suppression, disabled-state inertness, and window listener attach/detach.
//
// The guards that once lived in SwipePage (room-ready, match-found, modals) are
// folded into `enabled` by the caller, so they become `enabled: false`
// rerenders here rather than real modal clicks.
import { fireEvent, renderHook } from "@testing-library/react"
import { useSwipeDeckKeyboard } from "./useSwipeDeckKeyboard"

describe("useSwipeDeckKeyboard", () => {
  let onSwipe: (direction: "left" | "right") => void
  let onToggleDetails: () => void
  let focusButton: HTMLButtonElement | undefined

  beforeEach(() => {
    onSwipe = vi.fn()
    onToggleDetails = vi.fn()
  })

  afterEach(() => {
    if (focusButton) {
      focusButton.remove()
      focusButton = undefined
    }
  })

  it("commits a right swipe on ArrowRight", () => {
    renderHook(() => useSwipeDeckKeyboard({ enabled: true, onSwipe, onToggleDetails }))

    fireEvent.keyDown(window, { key: "ArrowRight" })

    expect(onSwipe).toHaveBeenCalledWith("right")
    expect(onToggleDetails).not.toHaveBeenCalled()
  })

  it("commits a left swipe on ArrowLeft", () => {
    renderHook(() => useSwipeDeckKeyboard({ enabled: true, onSwipe, onToggleDetails }))

    fireEvent.keyDown(window, { key: "ArrowLeft" })

    expect(onSwipe).toHaveBeenCalledWith("left")
    expect(onToggleDetails).not.toHaveBeenCalled()
  })

  it("flips details on ArrowUp", () => {
    renderHook(() => useSwipeDeckKeyboard({ enabled: true, onSwipe, onToggleDetails }))

    fireEvent.keyDown(window, { key: "ArrowUp" })

    expect(onToggleDetails).toHaveBeenCalledTimes(1)
    expect(onSwipe).not.toHaveBeenCalled()
  })

  it("flips details on Enter", () => {
    renderHook(() => useSwipeDeckKeyboard({ enabled: true, onSwipe, onToggleDetails }))

    fireEvent.keyDown(window, { key: "Enter" })

    expect(onToggleDetails).toHaveBeenCalledTimes(1)
    expect(onSwipe).not.toHaveBeenCalled()
  })

  it("does nothing when focus is on an interactive element", () => {
    renderHook(() => useSwipeDeckKeyboard({ enabled: true, onSwipe, onToggleDetails }))

    focusButton = document.createElement("button")
    document.body.appendChild(focusButton)
    focusButton.focus()

    fireEvent.keyDown(window, { key: "ArrowRight" })
    fireEvent.keyDown(window, { key: "Enter" })

    expect(onSwipe).not.toHaveBeenCalled()
    expect(onToggleDetails).not.toHaveBeenCalled()
  })

  it("does nothing while disabled", () => {
    const { rerender } = renderHook(
      ({ enabled }) => useSwipeDeckKeyboard({ enabled, onSwipe, onToggleDetails }),
      { initialProps: { enabled: true } },
    )

    rerender({ enabled: false })

    fireEvent.keyDown(window, { key: "ArrowRight" })
    fireEvent.keyDown(window, { key: "ArrowUp" })

    expect(onSwipe).not.toHaveBeenCalled()
    expect(onToggleDetails).not.toHaveBeenCalled()
  })

  it("detaches the listener after a disable", () => {
    const removeSpy = vi.spyOn(window, "removeEventListener")
    const { rerender } = renderHook(
      ({ enabled }) => useSwipeDeckKeyboard({ enabled, onSwipe, onToggleDetails }),
      { initialProps: { enabled: true } },
    )

    rerender({ enabled: false })

    expect(removeSpy).toHaveBeenCalledWith("keydown", expect.any(Function))
  })

  it("ignores key-repeat events", () => {
    renderHook(() => useSwipeDeckKeyboard({ enabled: true, onSwipe, onToggleDetails }))

    fireEvent.keyDown(window, { key: "ArrowRight", repeat: true })

    expect(onSwipe).not.toHaveBeenCalled()
    expect(onToggleDetails).not.toHaveBeenCalled()
  })

  it("lets an unmapped key fall through without preventDefault", () => {
    renderHook(() => useSwipeDeckKeyboard({ enabled: true, onSwipe, onToggleDetails }))

    const event = new KeyboardEvent("keydown", { key: "a", cancelable: true })
    const spy = vi.spyOn(event, "preventDefault")
    window.dispatchEvent(event)

    expect(onSwipe).not.toHaveBeenCalled()
    expect(onToggleDetails).not.toHaveBeenCalled()
    expect(spy).not.toHaveBeenCalled()
  })

  it("calls preventDefault for each mapped key", () => {
    renderHook(() => useSwipeDeckKeyboard({ enabled: true, onSwipe, onToggleDetails }))

    for (const key of ["ArrowLeft", "ArrowRight", "ArrowUp", "Enter"]) {
      const event = new KeyboardEvent("keydown", { key, cancelable: true })
      const spy = vi.spyOn(event, "preventDefault")
      window.dispatchEvent(event)
      expect(spy).toHaveBeenCalledTimes(1)
    }
  })

  it("does not preventDefault on a guard-rejected key", () => {
    renderHook(() => useSwipeDeckKeyboard({ enabled: true, onSwipe, onToggleDetails }))

    const event = new KeyboardEvent("keydown", { key: "Enter", repeat: true, cancelable: true })
    const spy = vi.spyOn(event, "preventDefault")
    window.dispatchEvent(event)

    expect(onToggleDetails).not.toHaveBeenCalled()
    expect(spy).not.toHaveBeenCalled()
  })
})
