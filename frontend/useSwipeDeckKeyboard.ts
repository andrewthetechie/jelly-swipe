import React from "react"

export interface UseSwipeDeckKeyboardOptions {
    /** Folded guard booleans: room-ready AND no match showing AND no modal open. */
    enabled: boolean
    onSwipe: (direction: "left" | "right") => void
    onToggleDetails: () => void
}

/**
 * Keyboard swipe support (issue #344): Left/Right swipe, Up/Enter flip.
 * Inert while any modal is open or an interactive element has focus (so
 * Enter always activates a focused button), and ignores key-repeat so a
 * held key cannot machine-gun swipes.
 *
 * Extracted from SwipePage (issue #419): takes plain callbacks and is agnostic
 * to the commit funnel; the guard booleans are folded into `enabled` by the
 * caller.
 */
export const useSwipeDeckKeyboard = ({
    enabled,
    onSwipe,
    onToggleDetails,
}: UseSwipeDeckKeyboardOptions): void => {
    // Hold the callbacks in refs so the window listener re-attaches only on
    // `enabled` transitions, never per keystroke.
    const onSwipeRef = React.useRef(onSwipe)
    const onToggleDetailsRef = React.useRef(onToggleDetails)
    React.useEffect(() => {
        onSwipeRef.current = onSwipe
        onToggleDetailsRef.current = onToggleDetails
    }, [onSwipe, onToggleDetails])

    React.useEffect(() => {
        if (!enabled) return
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.repeat) return

            const active = document.activeElement
            if (active instanceof HTMLElement) {
                const tag = active.tagName
                if (
                    tag === "BUTTON" ||
                    tag === "INPUT" ||
                    tag === "TEXTAREA" ||
                    tag === "SELECT" ||
                    active.isContentEditable
                ) {
                    return
                }
            }

            switch (e.key) {
                case "ArrowLeft":
                    e.preventDefault()
                    onSwipeRef.current("left")
                    break
                case "ArrowRight":
                    e.preventDefault()
                    onSwipeRef.current("right")
                    break
                case "ArrowUp":
                case "Enter":
                    e.preventDefault()
                    onToggleDetailsRef.current()
                    break
            }
        }
        window.addEventListener("keydown", handleKeyDown)
        return () => window.removeEventListener("keydown", handleKeyDown)
    }, [enabled])
}
