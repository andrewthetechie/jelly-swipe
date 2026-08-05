import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import GenreModal from "./GenreModal"
import { renderWithRoom, renderWithRoomStateful } from "./test/renderWithRoom"
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

        expect(await screen.findByLabelText("Action")).toBeInTheDocument()
        expect(screen.getByLabelText("Comedy")).toBeInTheDocument()
        expect(screen.getByLabelText("Drama")).toBeInTheDocument()

        expect(spy).toHaveBeenCalledOnce()

        const [url, options] = spy.mock.calls[0]

        expect((url as URL).href).toMatch(/\/genres$/)
        expect((options as RequestInit).method).toBe("GET")
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
    it("selected genre is checked", async () => {
        mockFetch({ ok: true, body: ["Action", "Comedy", "Drama"] })

        renderWithRoomStateful(
            <GenreModal 
                handleGenreClick={vi.fn()}
                handleGenreChange={vi.fn()}
            />,
            { genre: "Action", }
        )

        const action = await screen.findByLabelText("Action")
        expect(action).toBeChecked()
    })

    it("clicking another genre changes the selection", async () => {
        mockFetch({ ok: true, body: ["Action", "Comedy", "Drama"] })

        const user = userEvent.setup()

        renderWithRoomStateful(
            <GenreModal 
                handleGenreClick={vi.fn()}
                handleGenreChange={vi.fn()}
            />,
            { genre: "Action", }
        )

        const action = await screen.findByLabelText("Action")
        const comedy = screen.getByLabelText("Comedy")

        expect(action).toBeChecked()
        expect(comedy).not.toBeChecked()

        await user.click(comedy)

        expect(comedy).toBeChecked()
        expect(action).not.toBeChecked()
    })

    it("selecting another genre calls setGenre", async () => {
        mockFetch({ ok: true, body: ["Action", "Comedy", "Drama"] })

        const user = userEvent.setup()

        const { ctx } = renderWithRoom(
            <GenreModal 
                handleGenreClick={vi.fn()}
                handleGenreChange={vi.fn()}
            />,
            { genre: "Action", }
        )
        
        const comedy = await screen.findByLabelText("Comedy")
        await user.click(comedy)
        
        expect(ctx.setGenre).toHaveBeenCalledTimes(1)
        expect(ctx.setGenre).toHaveBeenCalledWith("Comedy")
    })
})

describe("GenreModal - buttons", () => {
    it("confirm button calls handleGenreChange", async () => {
        mockFetch({ ok: true, body: ["Action", "Comedy"] })

        const user = userEvent.setup()
        const { handleGenreChange } = renderGenreModal()

        await screen.findByLabelText("Action")

        await user.click(
            screen.getByRole("button", { name: /confirm/i, })
        )

        expect(handleGenreChange).toHaveBeenCalledOnce
    })

    it("cancel button calls handleGenreClick", async () => {
        mockFetch({ ok: true, body: ["Action", "Comedy"] })

        const user = userEvent.setup()
        const { handleGenreClick} = renderGenreModal()

        await screen.findByLabelText("Action")

        await user.click(
            screen.getByRole("button", { name: /cancel/i, })
        )

        expect(handleGenreClick).toHaveBeenCalledOnce
    })
})

describe("GenreModal - error path", () => {
    it("fetch failure does not load genres", async () => {
        const errSpy = vi.spyOn(console, "error").mockImplementation(() => {})

        const spy = mockFetch({ ok: false })

        renderGenreModal()

        await waitFor(() => {
            expect(spy).toHaveBeenCalledOnce()
        })

        expect(errSpy).toHaveBeenCalled()

        expect(
            screen.queryByLabelText("Action")
        ).not.toBeInTheDocument()

        expect(
            screen.queryByLabelText("Comedy")
        ).not.toBeInTheDocument()

        expect(
            screen.queryByLabelText("Drama")
        ).not.toBeInTheDocument()

        errSpy.mockRestore()
    })

    it("fetch rejection does not load genres", async () => {
        const errSpy = vi.spyOn(console, "error").mockImplementation(() => {})

        const spy = mockFetch({ reject: true })

        renderGenreModal()

        await waitFor(() => {
            expect(spy).toHaveBeenCalledOnce()
        })

        expect(errSpy).toHaveBeenCalled()

        expect(
            screen.queryByLabelText("Action")
        ).not.toBeInTheDocument()

        errSpy.mockRestore()
    })
})