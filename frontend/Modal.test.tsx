import { useState } from "react"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import Modal from "./Modal"
import type { ModalProps } from "./Modal"

function renderModal(overrides: Partial<ModalProps> = {}) {
    const onClose = vi.fn()
    const utils = render(
        <div>
            <button type="button">Open</button>
            <Modal onClose={onClose} labelledBy="modal-heading" {...overrides}>
                <h2 id="modal-heading">Test Dialog</h2>
                <button type="button">First</button>
                <button type="button">Last</button>
            </Modal>
        </div>,
    )
    return { onClose, ...utils }
}

// Controlled harness: the modal only mounts after the trigger button is clicked,
// which is how focus-return is exercised (the trigger holds focus when the
// dialog opens).
function TestHarness({ onClose }: { onClose: () => void }) {
    const [open, setOpen] = useState(false)
    return (
        <div>
            <button type="button" onClick={() => setOpen(true)}>Open</button>
            {open && (
                <Modal onClose={onClose} labelledBy="modal-heading">
                    <h2 id="modal-heading">Test Dialog</h2>
                    <button type="button">First</button>
                    <button type="button">Last</button>
                </Modal>
            )}
        </div>
    )
}

describe("Modal - accessibility attributes", () => {
    it("renders a dialog named by the heading id", () => {
        renderModal()
        const dialog = screen.getByRole("dialog")
        expect(dialog).toHaveAttribute("aria-modal", "true")
        expect(dialog).toHaveAttribute("aria-labelledby", "modal-heading")
        expect(screen.getByText("Test Dialog")).toBeInTheDocument()
    })

    it("applies the className prop to the inner content box", () => {
        renderModal({ className: "modal-genre" })
        expect(document.querySelector(".modal-inner")).toHaveClass("modal-genre")
    })
})

describe("Modal - dismissal", () => {
    it("Escape invokes onClose exactly once", async () => {
        const user = userEvent.setup()
        const { onClose } = renderModal()
        await user.keyboard("{Escape}")
        expect(onClose).toHaveBeenCalledTimes(1)
    })

    it("Escape pressed repeatedly still fires onClose only once per open cycle", async () => {
        const user = userEvent.setup()
        const { onClose } = renderModal()
        await user.keyboard("{Escape}{Escape}")
        expect(onClose).toHaveBeenCalledTimes(1)
    })

    it("clicking the overlay (dialog element) invokes onClose", async () => {
        const user = userEvent.setup()
        const { onClose } = renderModal()
        await user.click(screen.getByRole("dialog"))
        expect(onClose).toHaveBeenCalledTimes(1)
    })

    it("clicking inside the content box does not invoke onClose", async () => {
        const user = userEvent.setup()
        const { onClose } = renderModal()
        await user.click(screen.getByText("Test Dialog"))
        await user.click(screen.getByRole("button", { name: "First" }))
        expect(onClose).not.toHaveBeenCalled()
    })
})

describe("Modal - focus management", () => {
    it("moves focus into the dialog's first focusable control on open", () => {
        renderModal()
        expect(screen.getByRole("button", { name: "First" })).toHaveFocus()
    })

    it("restores focus to the triggering element after close", async () => {
        const user = userEvent.setup()
        const onClose = vi.fn()
        render(<TestHarness onClose={onClose} />)

        const trigger = screen.getByRole("button", { name: "Open" })
        await user.click(trigger)

        expect(screen.getByRole("dialog")).toBeInTheDocument()

        await user.keyboard("{Escape}")

        expect(onClose).toHaveBeenCalledTimes(1)
        expect(trigger).toHaveFocus()
    })

    it("restores focus to a programmatically-focused element on close", async () => {
        // Simulates programmatic open (e.g. MatchFoundModal via WebSocket): a
        // specific element already holds focus when the modal mounts, not from a
        // user click on a dedicated trigger.
        const user = userEvent.setup()
        const onClose = vi.fn()

        function ProgrammaticHarness({ open }: { open: boolean }) {
            return (
                <div>
                    <button type="button">Background</button>
                    {open && (
                        <Modal onClose={onClose} labelledBy="modal-heading">
                            <h2 id="modal-heading">Test Dialog</h2>
                            <button type="button">First</button>
                        </Modal>
                    )}
                </div>
            )
        }

        // Focus the background button before the modal mounts.
        const { getByRole, rerender } = render(<ProgrammaticHarness open={false} />)
        const bgBtn = getByRole("button", { name: "Background" })
        bgBtn.focus()
        expect(bgBtn).toHaveFocus()

        // Modal mounts programmatically — it captures bgBtn as the restore target.
        rerender(<ProgrammaticHarness open={true} />)
        expect(screen.getByRole("dialog")).toBeInTheDocument()

        await user.keyboard("{Escape}")

        expect(onClose).toHaveBeenCalledTimes(1)
        expect(bgBtn).toHaveFocus()
    })
})

describe("Modal - focus trap", () => {
    it("traps Tab and Shift+Tab inside the dialog", async () => {
        const user = userEvent.setup()
        renderModal()

        // Focus opens on the first focusable control.
        expect(screen.getByRole("button", { name: "First" })).toHaveFocus()

        await user.tab()
        expect(screen.getByRole("button", { name: "Last" })).toHaveFocus()

        // Wraps back to the first control instead of leaving the dialog.
        await user.tab()
        expect(screen.getByRole("button", { name: "First" })).toHaveFocus()

        // Shift+Tab wraps from the first control back to the last.
        await user.tab({ shift: true })
        expect(screen.getByRole("button", { name: "Last" })).toHaveFocus()
    })
})

describe("Modal - body scroll lock", () => {
    it("locks body scroll while open and restores it on close", async () => {
        const user = userEvent.setup()
        const { onClose } = renderModal()

        expect(document.body).toHaveClass("modal-open")

        await user.keyboard("{Escape}")

        expect(onClose).toHaveBeenCalledTimes(1)
        expect(document.body).not.toHaveClass("modal-open")
    })

    it("restores body scroll on unmount", () => {
        const { unmount } = renderModal()

        expect(document.body).toHaveClass("modal-open")

        unmount()
        expect(document.body).not.toHaveClass("modal-open")
    })

    it("keeps body scroll locked until the last stacked dialog closes", async () => {
        const user = userEvent.setup()
        const onCloseA = vi.fn()
        const onCloseB = vi.fn()
        const utils = render(
            <div>
                <Modal onClose={onCloseA} labelledBy="heading-a">
                    <h2 id="heading-a">Dialog A</h2>
                    <button type="button">A First</button>
                </Modal>
                <Modal onClose={onCloseB} labelledBy="heading-b">
                    <h2 id="heading-b">Dialog B</h2>
                    <button type="button">B First</button>
                </Modal>
            </div>,
        )

        expect(document.body).toHaveClass("modal-open")

        // Close one of the two dialogs; the other still holds the scroll lock.
        await user.keyboard("{Escape}")
        expect(onCloseA.mock.calls.length + onCloseB.mock.calls.length).toBe(1)
        expect(document.body).toHaveClass("modal-open")

        // Unmount the remaining dialog; the lock is released.
        utils.unmount()
        expect(document.body).not.toHaveClass("modal-open")
    })
})
