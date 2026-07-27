import { screen, render, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import MatchListModal from "./MatchListModal"
import { makeMatch } from "./test/fixtures"
import { makeMatchList } from "./test/fixtures"
import { mockFetch } from "./test/mockFetch"

describe("MatchListModal - Match List Fetch", () => {
    it("successful GET renders match list", async () => {
        const matchList = makeMatchList(2)
        mockFetch({
            ok: true,
            body: { matches: matchList }
        })

        render(<MatchListModal handleMatchListClick={vi.fn()} />)

        expect(await screen.findByText("Movie 1")).toBeInTheDocument()
        expect(screen.getByText("Movie 2")).toBeInTheDocument()
    })

    it("failed GET leaves list empty", async () => {
        const errSpy = vi.spyOn(console, "error").mockImplementation(() => {})

        const spy = mockFetch({ ok: false })

        render(<MatchListModal handleMatchListClick={vi.fn()} />)

        await waitFor(() => {
            expect(spy).toHaveBeenCalledOnce()
        })

        expect(errSpy).toHaveBeenCalled()

        expect(screen.queryByText("Movie 1")).not.toBeInTheDocument()
        expect(screen.getByText("Match List")).toBeInTheDocument()
        expect(
            screen.getByRole("button", { name: /keep swiping/i })
        ).toBeInTheDocument()

        errSpy.mockRestore()
    })

    it("GET sends the correct endpoint and method", async () => {
        const matchList = makeMatchList(2)
        const spy = mockFetch({
            ok: true,
            body: { matches: matchList }
        })

        render(<MatchListModal handleMatchListClick={vi.fn()} />)    
        
        await waitFor(() => {
            expect(spy).toHaveBeenCalledOnce()
        })

        const [url, options] = spy.mock.calls[0]

        expect((url as URL).href).toMatch(/\/matches$/)
        expect(options.method).toBe("GET")
    })
})

describe("MatchListModal - rendering", () => {
    it("renders match metadata correctly", async () => {
        const matchList = makeMatchList(1)
        mockFetch({
            ok: true,
            body: { matches: matchList }
        })

        render(<MatchListModal handleMatchListClick={vi.fn()} />)

        expect(await screen.findByText("Movie 1")).toBeInTheDocument()
        expect(screen.getByText("IMDb 8.25")).toBeInTheDocument()
        expect(screen.getByText("107 min")).toBeInTheDocument()
        expect(screen.getByText("2016")).toBeInTheDocument()
        expect(screen.getByAltText("Movie 1")).toBeInTheDocument()
        expect(
            screen.getByRole("link", {
                name: /open in jellyfin/i,
            })
        ).toHaveAttribute(
            "href",
            "https://jellyfin.example.com/web/index.html#!/details?id=movie-1"
        )
    })

    it("Keep Swiping button calls handleMatchListClick", async () => {
        const user = userEvent.setup()
        const handleMatchListClick = vi.fn()
        const matchList = makeMatchList(1)
        mockFetch({
            ok: true,
            body: { matches: matchList }
        })

        render(<MatchListModal handleMatchListClick={handleMatchListClick} />)

        await screen.findByAltText("Movie 1")
        await user.click(
            screen.getByRole("button", { name: /keep swiping/i })
        )

        expect(handleMatchListClick).toHaveBeenCalledOnce()
    })

    it("omits option rating/runtime when missing from data", async () => {
        const matchList = [makeMatch({ rating: null, duration: null })]
        mockFetch({
            ok: true,
            body: { matches: matchList }
        })

        render(<MatchListModal handleMatchListClick={vi.fn()} />)

        expect(await screen.findByText("Movie 1")).toBeInTheDocument()

        expect(screen.queryByText("IMDb 8.25")).not.toBeInTheDocument()
        expect(screen.queryByText("107 min")).not.toBeInTheDocument()
    })

    it("renders correctly with an empty match list", async () => {
        const spy = mockFetch({
            ok: true,
            body: { matches: [] }
        })

        render(<MatchListModal handleMatchListClick={vi.fn()} />)

        await waitFor(() => {
            expect(spy).toHaveBeenCalledOnce()
        })

        expect(screen.getByText("Match List")).toBeInTheDocument()
        expect(
            screen.getByRole("button", { name: /keep swiping/i })
        ).toBeInTheDocument()
        expect(screen.queryByRole("link", {
            name: /open in jellyfin/i,
        })).not.toBeInTheDocument()
            })
})