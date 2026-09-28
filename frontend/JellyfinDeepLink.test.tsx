import { screen, render } from "@testing-library/react"
import JellyfinDeepLink from "./JellyfinDeepLink"

describe("JellyfinDeepLink", () => {
    it("renders a link when deepLink is provided", () => {
        render(
            <JellyfinDeepLink
                deepLink="https://jellyfin.example.com/web/index.html#!/details?id=movie-1"
                className="btn-primary"
                linkClassName="btn-primary btn-primary-link"
            />
        )

        const link = screen.getByRole("link", {
            name: /Open in Jellyfin 🍿/i
        })

        expect(link).toHaveAttribute(
            "href",
            "https://jellyfin.example.com/web/index.html#!/details?id=movie-1"
        )
        expect(link).toHaveAttribute("target", "_blank")
        expect(link).toHaveAttribute("rel", "noopener noreferrer")
        expect(link).toHaveClass("btn-primary btn-primary-link")
    })

    it("renders a disabled button when there is no deepLink", () => {
        render(
            <JellyfinDeepLink
                deepLink={null}
                className="btn-secondary match-list-button"
                linkClassName="btn-secondary match-list-button"
            />
        )

        const button = screen.getByRole("button", {
            name: /open in jellyfin 🍿/i
        })

        expect(button).toBeDisabled()
        expect(button).toHaveClass("btn-secondary match-list-button")
        expect(screen.queryByRole("link", {
            name: /open in jellyfin 🍿/i
        })).not.toBeInTheDocument()
        expect(document.querySelector('[href="#"]')).not.toBeInTheDocument()
    })
})
