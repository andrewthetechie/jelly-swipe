import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import GenreModal from "./GenreModal"
import { renderWithRoom, renderWithRoomStateful } from "./test/renderWithRoom"
import * as roomApi from "./roomApi"

vi.mock("./roomApi", () => ({
  fetchGenres: vi.fn(),
  setGenreChoice: vi.fn(),
}))

const fetchGenresMock = vi.mocked(roomApi.fetchGenres)
const setGenreChoiceMock = vi.mocked(roomApi.setGenreChoice)

beforeEach(() => {
  sessionStorage.clear()
  vi.restoreAllMocks()
  vi.clearAllMocks()
  fetchGenresMock.mockResolvedValue(["Action", "Comedy", "Drama"])
  setGenreChoiceMock.mockResolvedValue({ deck: [], mutationEventId: 1, mutationType: "genre_changed" })
})

function renderGenreModal() {
  const handleGenreClick = vi.fn()

  const utils = renderWithRoom(
    <GenreModal handleGenreClick={handleGenreClick} />,
    {
      currentRoomCode: "1234",
      genre: "All",
    },
  )

  return {
    ...utils,
    handleGenreClick,
  }
}

describe("GenreModal - data loading and caching", () => {
  it("renders fetched genres", async () => {
    renderGenreModal()

    expect(await screen.findByLabelText("Action")).toBeInTheDocument()
    expect(screen.getByLabelText("Comedy")).toBeInTheDocument()
    expect(screen.getByLabelText("Drama")).toBeInTheDocument()

    expect(fetchGenresMock).toHaveBeenCalledOnce()
  })

  it("uses cached genres instead of fetching them", () => {
    sessionStorage.setItem("genres", JSON.stringify(["Action", "Comedy"]))

    renderGenreModal()

    expect(screen.getByLabelText("Action")).toBeInTheDocument()
    expect(screen.getByLabelText("Comedy")).toBeInTheDocument()

    expect(fetchGenresMock).not.toHaveBeenCalled()
  })

  it("caches fetched genres", async () => {
    renderGenreModal()

    expect(await screen.findByLabelText("Action")).toBeInTheDocument()

    expect(JSON.parse(sessionStorage.getItem("genres")!)).toEqual([
      "Action",
      "Comedy",
      "Drama",
    ])
  })
})

describe("GenreModal - radio group behavior", () => {
  it("selected genre is checked", async () => {
    renderWithRoomStateful(
      <GenreModal handleGenreClick={vi.fn()} />,
      { genre: "Action" },
    )

    const action = await screen.findByLabelText("Action")
    expect(action).toBeChecked()
  })

  it("clicking another genre changes the selection", async () => {
    const user = userEvent.setup()

    renderWithRoomStateful(
      <GenreModal handleGenreClick={vi.fn()} />,
      { genre: "Action" },
    )

    const action = await screen.findByLabelText("Action")
    const comedy = screen.getByLabelText("Comedy")

    expect(action).toBeChecked()
    expect(comedy).not.toBeChecked()

    await user.click(comedy)

    expect(comedy).toBeChecked()
    expect(action).not.toBeChecked()
  })
})

describe("GenreModal - buttons", () => {
  it("confirm button calls roomApi.setGenreChoice with current room code + genre", async () => {
    const user = userEvent.setup()
    renderGenreModal()

    await screen.findByLabelText("Action")

    await user.click(screen.getByRole("button", { name: /confirm/i }))

    await waitFor(() => expect(setGenreChoiceMock).toHaveBeenCalledTimes(1))
    expect(setGenreChoiceMock).toHaveBeenCalledWith("1234", "All")
  })

  it("cancel button calls handleGenreClick", async () => {
    const user = userEvent.setup()
    const { handleGenreClick } = renderGenreModal()

    await screen.findByLabelText("Action")

    await user.click(screen.getByRole("button", { name: /cancel/i }))

    expect(handleGenreClick).toHaveBeenCalledOnce()
  })
})

describe("GenreModal - error path", () => {
  it("fetch failure does not load genres", async () => {
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {})
    fetchGenresMock.mockRejectedValueOnce(new Error("Error fetching genres"))

    renderGenreModal()

    await waitFor(() => {
      expect(fetchGenresMock).toHaveBeenCalledOnce()
    })

    expect(errSpy).toHaveBeenCalled()
    expect(screen.queryByLabelText("Action")).not.toBeInTheDocument()
    expect(screen.queryByLabelText("Comedy")).not.toBeInTheDocument()
    expect(screen.queryByLabelText("Drama")).not.toBeInTheDocument()

    errSpy.mockRestore()
  })

  it("fetch rejection does not load genres", async () => {
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {})
    fetchGenresMock.mockRejectedValueOnce(new Error("network error"))

    renderGenreModal()

    await waitFor(() => {
      expect(fetchGenresMock).toHaveBeenCalledOnce()
    })

    expect(errSpy).toHaveBeenCalled()
    expect(screen.queryByLabelText("Action")).not.toBeInTheDocument()

    errSpy.mockRestore()
  })
})
