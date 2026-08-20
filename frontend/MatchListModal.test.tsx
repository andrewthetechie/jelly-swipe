import { screen, render, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import MatchListModal from "./MatchListModal"
import { makeMatch, makeMatchList } from "./test/fixtures"
import * as roomApi from "./roomApi"

vi.mock("./roomApi", () => ({
  fetchMatches: vi.fn(),
}))

const fetchMatchesMock = vi.mocked(roomApi.fetchMatches)

beforeEach(() => {
  vi.clearAllMocks()
  fetchMatchesMock.mockResolvedValue(makeMatchList(2))
})

describe("MatchListModal - Match List Fetch", () => {
  it("successful fetch renders match list", async () => {
    const matchList = makeMatchList(2)
    fetchMatchesMock.mockResolvedValueOnce(matchList)

    render(<MatchListModal handleMatchListClick={vi.fn()} />)

    expect(await screen.findByText("Movie 1")).toBeInTheDocument()
    expect(screen.getByText("Movie 2")).toBeInTheDocument()
    expect(screen.queryByText("No Matches Yet!")).not.toBeInTheDocument()
  })

  it("failed fetch leaves list empty", async () => {
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {})
    fetchMatchesMock.mockRejectedValueOnce(new Error("Error retrieving matches"))

    render(<MatchListModal handleMatchListClick={vi.fn()} />)

    await waitFor(() => {
      expect(fetchMatchesMock).toHaveBeenCalledOnce()
    })

    expect(errSpy).toHaveBeenCalled()
    expect(screen.queryByText("Movie 1")).not.toBeInTheDocument()
    expect(screen.getByText("Match List")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /keep swiping/i })).toBeInTheDocument()

    errSpy.mockRestore()
  })
})

describe("MatchListModal - rendering", () => {
  it("renders match metadata correctly", async () => {
    const matchList = makeMatchList(1)
    fetchMatchesMock.mockResolvedValueOnce(matchList)

    render(<MatchListModal handleMatchListClick={vi.fn()} />)

    expect(await screen.findByText("Movie 1")).toBeInTheDocument()
    expect(screen.getByText("IMDb 8.25")).toBeInTheDocument()
    expect(screen.getByText("107 min")).toBeInTheDocument()
    expect(screen.getByText("2016")).toBeInTheDocument()
    expect(screen.getByAltText("Movie 1")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /open in jellyfin/i })).toHaveAttribute(
      "href",
      "https://jellyfin.example.com/web/index.html#!/details?id=movie-1",
    )
  })

  it("Keep Swiping button calls handleMatchListClick", async () => {
    const user = userEvent.setup()
    const handleMatchListClick = vi.fn()
    fetchMatchesMock.mockResolvedValueOnce(makeMatchList(1))

    render(<MatchListModal handleMatchListClick={handleMatchListClick} />)

    await screen.findByAltText("Movie 1")
    await user.click(screen.getByRole("button", { name: /keep swiping/i }))

    expect(handleMatchListClick).toHaveBeenCalledOnce()
  })

  it("omits optional rating/runtime when missing from data", async () => {
    fetchMatchesMock.mockResolvedValueOnce([makeMatch({ rating: null, duration: null })])

    render(<MatchListModal handleMatchListClick={vi.fn()} />)

    expect(await screen.findByText("Movie 1")).toBeInTheDocument()
    expect(screen.queryByText("IMDb 8.25")).not.toBeInTheDocument()
    expect(screen.queryByText("107 min")).not.toBeInTheDocument()
  })

  it("renders correctly with an empty match list", async () => {
    fetchMatchesMock.mockResolvedValueOnce([])

    render(<MatchListModal handleMatchListClick={vi.fn()} />)

    await waitFor(() => {
      expect(fetchMatchesMock).toHaveBeenCalledOnce()
    })

    expect(screen.getByText("Match List")).toBeInTheDocument()
    expect(screen.getByText("No Matches Yet!")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /keep swiping/i })).toBeInTheDocument()
    expect(screen.queryByRole("link", { name: /open in jellyfin/i })).not.toBeInTheDocument()
  })
})
