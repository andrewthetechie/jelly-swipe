
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { render, screen } from "@testing-library/react"
import ActorElements from "./ActorElements"
import * as useMovieCastModule from "./useMovieCast"
import { makeCastMember, makeCast } from "./test/fixtures"

vi.mock("./useMovieCast")

describe("ActorElements", () => {
  let useMovieCastSpy: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    const mockModule = useMovieCastModule as any
    useMovieCastSpy = mockModule.default
    useMovieCastSpy.mockReturnValue({
      cast: [],
      isLoading: false,
      error: null,
    })
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe("loading state", () => {
    it("renders loading message when isLoading is true", () => {
      const mockModule = useMovieCastModule as any
      mockModule.default.mockReturnValue({
        cast: [],
        isLoading: true,
        error: null,
      })

      render(<ActorElements mediaId="m1" />)
      expect(screen.getByText("Loading cast...")).toBeInTheDocument()
    })
  })

  describe("error and empty states", () => {
    it("renders error message when error is set", () => {
      const mockModule = useMovieCastModule as any
      mockModule.default.mockReturnValue({
        cast: [],
        isLoading: false,
        error: "Failed to fetch",
      })

      render(<ActorElements mediaId="m1" />)
      expect(screen.getByText("Unable to load cast")).toBeInTheDocument()
    })

    it("renders error message when cast is empty", () => {
      const mockModule = useMovieCastModule as any
      mockModule.default.mockReturnValue({
        cast: [],
        isLoading: false,
        error: null,
      })

      render(<ActorElements mediaId="m1" />)
      expect(screen.getByText("Unable to load cast")).toBeInTheDocument()
    })
  })

  describe("cast rendering", () => {
    it("renders each actor's name and profile image", () => {
      const mockModule = useMovieCastModule as any
      const cast = [
        makeCastMember({ name: "Alice", profile_path: "/alice.jpg" }),
        makeCastMember({ name: "Bob", profile_path: "/bob.jpg" }),
      ]
      mockModule.default.mockReturnValue({
        cast,
        isLoading: false,
        error: null,
      })

      render(<ActorElements mediaId="m1" />)

      expect(screen.getByText("Alice")).toBeInTheDocument()
      expect(screen.getByAltText("Alice profile")).toHaveAttribute("src", "/alice.jpg")

      expect(screen.getByText("Bob")).toBeInTheDocument()
      expect(screen.getByAltText("Bob profile")).toHaveAttribute("src", "/bob.jpg")
    })

    it("uses fallback image when profile_path is null", () => {
      const mockModule = useMovieCastModule as any
      const cast = [makeCastMember({ name: "Charlie", profile_path: null })]
      mockModule.default.mockReturnValue({
        cast,
        isLoading: false,
        error: null,
      })

      render(<ActorElements mediaId="m1" />)

      expect(screen.getByText("Charlie")).toBeInTheDocument()

      const fallbackImg = screen.getByAltText("Charlie profile picture not available")
      expect(fallbackImg).toBeInTheDocument()
      expect(fallbackImg.className).toBe("actor-image")
    })

    it("renders multiple cast members with distinct keys", () => {
      const mockModule = useMovieCastModule as any
      const cast = makeCast(3)
      mockModule.default.mockReturnValue({
        cast,
        isLoading: false,
        error: null,
      })

      render(<ActorElements mediaId="m123" />)

      expect(screen.getByText("Actor 1")).toBeInTheDocument()
      expect(screen.getByText("Actor 2")).toBeInTheDocument()
      expect(screen.getByText("Actor 3")).toBeInTheDocument()

      const { container } = render(<ActorElements mediaId="m123" />)
      const cards = container.querySelectorAll(".actor-card")
      expect(cards).toHaveLength(3)
    })
  })
})

