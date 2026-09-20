import { fireEvent, render, screen } from "@testing-library/react"
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

    it("falls back to the sad image + label when the poster URL errors", () => {
        render(<PosterImage posterUrl="https://example.com/broken.jpg" alt="Moana" frame showNoPosterLabel />)
        const img = screen.getByAltText("Moana")
        fireEvent.error(img)
        expect(img.getAttribute("src")).toContain("sad")
        expect(screen.getByText("No poster available")).toBeInTheDocument()
        // The broken image icon is never rendered — the img keeps the fallback src.
        expect(img.getAttribute("src")).not.toBe("https://example.com/broken.jpg")
    })

    it("marks the frame loaded (fade-in) only after the poster loads", () => {
        const { container } = render(<PosterImage posterUrl="https://example.com/poster.jpg" alt="Moana" frame />)
        const frame = container.querySelector(".poster-frame") as HTMLElement
        expect(frame).not.toHaveClass("poster-frame-loaded")
        fireEvent.load(screen.getByAltText("Moana"))
        expect(frame).toHaveClass("poster-frame-loaded")
    })

    it("sets decoding=async on every img and fetchpriority=high only when priority", () => {
        const { rerender } = render(<PosterImage posterUrl="https://example.com/poster.jpg" alt="Moana" />)
        const img = screen.getByAltText("Moana")
        expect(img).toHaveAttribute("decoding", "async")
        expect(img.getAttribute("fetchpriority")).toBeNull()

        rerender(<PosterImage posterUrl="https://example.com/poster.jpg" alt="Moana" priority />)
        expect(img.getAttribute("fetchpriority")).toBe("high")
    })

    it("only wraps in the reserved frame when frame is requested", () => {
        const { container, rerender } = render(<PosterImage posterUrl="https://example.com/poster.jpg" alt="Moana" />)
        expect(container.querySelector(".poster-frame")).toBeNull()

        rerender(<PosterImage posterUrl="https://example.com/poster.jpg" alt="Moana" frame />)
        expect(container.querySelector(".poster-frame")).not.toBeNull()
    })
})
