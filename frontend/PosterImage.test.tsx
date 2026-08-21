import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import PosterImage from "./PosterImage"

describe("PosterImage", () => {
    it("renders the poster when posterUrl is set", () => {
        render(<PosterImage posterUrl="https://example.com/poster.jpg" alt="Moana" />)
        expect(screen.getByAltText("Moana")).toHaveAttribute("src", "https://example.com/poster.jpg")
    })

    it("falls back to the placeholder image when posterUrl is null", () => {
        render(<PosterImage posterUrl={null} alt="Moana" />)
        expect(screen.getByAltText("Moana").getAttribute("src")).toContain("sad")
    })

    it("shows 'No poster available' only when asked AND there is no poster", () => {
        const { rerender } = render(<PosterImage posterUrl={null} alt="Moana" />)
        expect(screen.queryByText("No poster available")).not.toBeInTheDocument()

        rerender(<PosterImage posterUrl={null} alt="Moana" showNoPosterLabel />)
        expect(screen.getByText("No poster available")).toBeInTheDocument()

        rerender(<PosterImage posterUrl="https://example.com/p.jpg" alt="Moana" showNoPosterLabel />)
        expect(screen.queryByText("No poster available")).not.toBeInTheDocument()
    })
})