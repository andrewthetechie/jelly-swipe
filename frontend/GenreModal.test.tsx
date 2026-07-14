import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import GenreModal from "./GenreModal"
import { renderWithRoom } from "./test/renderWithRoom"
import { mockFetch } from "./test/mockFetch"

beforeEach(() => {
    sessionStorage.clear()
    vi.restoreAllMocks()
})

afterEach(() => {
    vi.clearAllMocks()
})

function renderGenreModal() {
    const handleGenreClick = vi.fn()
    const handleGenreChange = vi.fn()

    const utils = renderWithRoom(
        <GenreModal 
            handleGenreClick={handleGenreClick}
            handleGenreChange={handleGenreChange}
        />,
        {
            currentRoomCode: "1234",
            genre: "All"
        }
    )

    return {
        ...utils,
        handleGenreClick,
        handleGenreChange,
    }
}

describe("GenreModal - data loading and caching", () => {
    it("renders fetched genres", async () => {
        const spy = mockFetch({ ok: true, body: ["Action", "Comedy", "Drama"] })
        renderGenreModal()

        const [url, options] = spy.mock.calls[0]

        expect((url as URL).href).toMatch(/\/genres$/)
        expect((options as RequestInit).method).toBe("GET")

        expect(await screen.findByLabelText("Action")).toBeInTheDocument()
        expect(screen.getByLabelText("Comedy")).toBeInTheDocument()
        expect(screen.getByLabelText("Drama")).toBeInTheDocument()
    })

    it("uses cached genres instead of fetching them", () => {
        sessionStorage.setItem(
            "genres",
            JSON.stringify(["Action", "Comedy"])
        )

        const fetchSpy = vi.spyOn(globalThis, "fetch")

        renderGenreModal()

        expect(screen.getByLabelText("Action")).toBeInTheDocument()
        expect(screen.getByLabelText("Comedy")).toBeInTheDocument()

        expect(fetchSpy).not.toHaveBeenCalled()
    })

    it("caches fetched genres", async () => {
        mockFetch({ ok: true, body: ["Action", "Comedy", "Drama"] })
        renderGenreModal()

        expect(await screen.findByLabelText("Action")).toBeInTheDocument()

        expect(
            JSON.parse(
                sessionStorage.getItem("genres")!
            )
        ).toEqual([
            "Action", "Comedy", "Drama"
        ])
    })
})

describe("GenreModal - radio group behavior", () => {
    it("selected genre is checked", () => {

    })

    it("clicking another genre changes the selection", () => {

    })
})

describe("GenreModal - buttons", () => {
    it("confirm button calls handleGenreChange", () => {

    })

    it("cancel button calls handleGenreClick", () => {

    })
})

describe("GenreModal - error path", () => {
    it("fetch failure does not load genres", () => {

    })
})