import { useEffect, useRef } from "react"
import type { JSX, ReactNode } from "react"

export interface ModalProps {
    /** Fired at most once per open cycle when the dialog is dismissed (Escape, overlay click, or a consumer Cancel button). */
    onClose: () => void
    /** id of the heading that names the dialog; used via aria-labelledby. */
    labelledBy: string
    /** Optional class applied to the inner content box (e.g. modal-genre / modal-match-list). */
    className?: string
    children: ReactNode
}

const FOCUSABLE_SELECTOR = [
    "button:not([disabled])",
    "[href]",
    "input:not([disabled])",
    "select:not([disabled])",
    "textarea:not([disabled])",
    "[tabindex]:not([tabindex='-1'])",
].join(",")

// Reference count of open dialogs. `modal-open` is added to <body> only when the
// first dialog opens (0→1) and removed only when the last one closes (1→0), so a
// stack of dialogs keeps the page scroll-locked until every dialog is gone.
let openDialogCount = 0

function lockBodyScroll() {
    openDialogCount += 1
    if (openDialogCount === 1) document.body.classList.add("modal-open")
}

function unlockBodyScroll() {
    if (openDialogCount === 0) return
    openDialogCount -= 1
    if (openDialogCount === 0) document.body.classList.remove("modal-open")
}

export default function Modal({ onClose, labelledBy, className, children }: ModalProps): JSX.Element {
    const dialogRef = useRef<HTMLDialogElement>(null)
    const onCloseRef = useRef(onClose)

    // Keep the ref holding the freshest onClose after every render so dismissal
    // event handlers always call the latest callback without re-subscribing.
    useEffect(() => {
        onCloseRef.current = onClose
    })

    useEffect(() => {
        const dialog = dialogRef.current
        if (!dialog) return

        // Guard so onClose fires at most once per open cycle. A native <dialog>
        // can emit both `cancel` and `close` for a single Escape press, and our
        // own keydown handler also sees the Escape, so every dismissal path
        // funnels through this single guarded callback.
        let closeFired = false
        // Guard so this instance releases the scroll lock at most once per open
        // cycle: fireClose unlocks, then the consumer's onClose typically unmounts
        // the Modal, whose cleanup would otherwise unlock (and decrement) again.
        let scrollUnlocked = false
        const trigger = document.activeElement as HTMLElement | null

        const releaseScrollLock = () => {
            if (scrollUnlocked) return
            scrollUnlocked = true
            unlockBodyScroll()
        }
        const restoreFocus = () => {
            if (trigger && trigger !== document.body) trigger.focus()
        }

        const fireClose = () => {
            if (closeFired) return
            closeFired = true
            releaseScrollLock()
            restoreFocus()
            dialog.close()
            onCloseRef.current()
        }

        const trapFocus = (e: KeyboardEvent) => {
            const focusables = Array.from(dialog.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR))
            if (focusables.length === 0) {
                e.preventDefault()
                dialog.focus()
                return
            }
            const first = focusables[0]
            const last = focusables[focusables.length - 1]
            const active = document.activeElement
            const inside = dialog.contains(active)

            if (e.shiftKey) {
                if (!inside || active === first) {
                    e.preventDefault()
                    last.focus()
                }
            } else if (!inside || active === last) {
                e.preventDefault()
                first.focus()
            }
        }

        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === "Escape") {
                e.preventDefault()
                fireClose()
            } else if (e.key === "Tab") {
                trapFocus(e)
            }
        }

        const handleOverlayPointer = (e: PointerEvent) => {
            // Overlay click = a pointerdown whose target is the dialog element
            // itself rather than the inner content box.
            if (e.target === dialog) fireClose()
        }

        const handleCancel = (e: Event) => {
            // Native <dialog> fires `cancel` on Escape. Route it through the
            // same guarded callback as the keydown handler so it stays a single
            // onClose call.
            e.preventDefault()
            fireClose()
        }

        dialog.showModal()
        lockBodyScroll()

        // Move focus into the dialog: its first focusable control, else the
        // dialog itself.
        const focusTarget = dialog.querySelector<HTMLElement>(FOCUSABLE_SELECTOR) ?? dialog
        focusTarget.focus()

        dialog.addEventListener("keydown", handleKeyDown)
        dialog.addEventListener("pointerdown", handleOverlayPointer)
        dialog.addEventListener("cancel", handleCancel)

        return () => {
            dialog.removeEventListener("keydown", handleKeyDown)
            dialog.removeEventListener("pointerdown", handleOverlayPointer)
            dialog.removeEventListener("cancel", handleCancel)
            releaseScrollLock()
            restoreFocus()
        }
    }, [])

    return (
        <dialog
            ref={dialogRef}
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby={labelledBy}
        >
            <div className={`modal-inner${className ? ` ${className}` : ""}`}>{children}</div>
        </dialog>
    )
}
