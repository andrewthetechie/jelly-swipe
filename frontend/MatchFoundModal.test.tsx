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
                onClick={vi.fn()}
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
                onClick={vi.fn()}
            />
        )

        expect(screen.getByText("2026")).toBeInTheDocument()
        expect(screen.getByText("IMDb 9.25")).toBeInTheDocument()
        expect(screen.getByText("52 min")).toBeInTheDocument()
    })

    it("renders the correct poster", () => {
        const match = makeMatch({
            title: "Moana",
            thumb: "/moana-poster.jpg",
        })

        render(
            <MatchFoundModal
                matchItem={match}
                onClick={vi.fn()}
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
            deep_link: "https://jellyfin.example.com/web/index.html#!/details?id=movie-1",
        })

        render(
            <MatchFoundModal
                matchItem={match}
                onClick={vi.fn()}
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

    it("falls back to # when there is no deepLink", () => {
        const match = makeMatch({
            deep_link: null,
        })

        render(
            <MatchFoundModal
                matchItem={match}
                onClick={vi.fn()}
            />
        )

        const link = screen.getByRole("link", {
            name: /open in jellyfin 🍿/i
        })

        expect(link).toHaveAttribute(
            "href",
            "#"
        )
    })
})

describe("MatchFoundModal - keep swiping button", () => {
    it("clicking Keep Swiping button calls onClick", async () => {
        const onClick = vi.fn()
        const user = userEvent.setup()

        render (
            <MatchFoundModal
                matchItem={makeMatch()}
                onClick={onClick}
            />
        )

        await user.click(
            screen.getByRole("button", {
                name: /keep swiping/i
            })
        )

        expect(onClick).toHaveBeenCalledOnce()
    })
})
