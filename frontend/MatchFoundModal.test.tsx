import { screen, render } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import MatchFoundModal from "./MatchFoundModal"
import { makeMatch } from "./test/fixtures"

describe("MatchFoundModal - rendering", () => {
    it("renders the correct title", () => {
        const match = makeMatch({
            title: "Moana",
        })

        render(
            <MatchFoundModal
                matchItem={match}
                onClose={vi.fn()}
            />
        )

        expect(screen.getByRole("heading", { name: "Moana" })).toBeInTheDocument()
    })

    it("renders the correct metadata", () => {
        const match = makeMatch({
            year: 2026,
            rating: 9.25,
            duration: "52 min",
        })

        render(
            <MatchFoundModal
                matchItem={match}
                onClose={vi.fn()}
            />
        )

        expect(screen.getByText("2026")).toBeInTheDocument()
        expect(screen.getByText("IMDb 9.25")).toBeInTheDocument()
        expect(screen.getByText("52 min")).toBeInTheDocument()
    })

    it("renders the correct poster", () => {
        const match = makeMatch({
            title: "Moana",
            posterUrl: "/moana-poster.jpg",
        })

        render(
            <MatchFoundModal
                matchItem={match}
                onClose={vi.fn()}
            />
        )

        const poster = screen.getByRole("img", {
            name: "Moana"
        }) as HTMLImageElement

        expect(poster).toBeInTheDocument()
        expect(poster.src).toBe(new URL("/moana-poster.jpg", window.location.origin).href)
    })
})

describe("MatchFoundModal - watch on Jellyfin functionality", () => {
    it("uses deepLink when provided", () => {
        const match = makeMatch({
            deepLink: "https://jellyfin.example.com/web/index.html#!/details?id=movie-1",
        })

        render(
            <MatchFoundModal
                matchItem={match}
                onClose={vi.fn()}
            />
        )

        const link = screen.getByRole("link", {
            name: /Open in Jellyfin 🍿/i
        })

        expect(link).toHaveAttribute(
            "href",
            "https://jellyfin.example.com/web/index.html#!/details?id=movie-1"
        )
    })

    it("renders a disabled button when there is no deepLink", () => {
        const match = makeMatch({
            deepLink: null,
        })

        render(
            <MatchFoundModal
                matchItem={match}
                onClose={vi.fn()}
            />
        )

        const button = screen.getByRole("button", {
            name: /open in jellyfin 🍿/i
        })

        expect(button).toBeDisabled()
        expect(screen.queryByRole("link", {
            name: /open in jellyfin 🍿/i
        })).not.toBeInTheDocument()
        expect(document.querySelector('[href="#"]')).not.toBeInTheDocument()
    })
})

describe("MatchFoundModal - keep swiping button", () => {
    it("clicking Keep Swiping button calls onClose", async () => {
        const onClose = vi.fn()
        const user = userEvent.setup()

        render (
            <MatchFoundModal
                matchItem={makeMatch()}
                onClose={onClose}
            />
        )

        await user.click(
            screen.getByRole("button", {
                name: /keep swiping/i
            })
        )

        expect(onClose).toHaveBeenCalledOnce()
    })

    it("Escape dismisses the match via onClose", async () => {
        const onClose = vi.fn()
        const user = userEvent.setup()

        render(
            <MatchFoundModal
                matchItem={makeMatch()}
                onClose={onClose}
            />
        )

        await user.keyboard("{Escape}")

        expect(onClose).toHaveBeenCalledOnce()
    })

    it("overlay click dismisses the match via onClose", async () => {
        const onClose = vi.fn()
        const user = userEvent.setup()

        render(
            <MatchFoundModal
                matchItem={makeMatch()}
                onClose={onClose}
            />
        )

        await user.click(screen.getByRole("dialog"))

        expect(onClose).toHaveBeenCalledOnce()
    })
})
