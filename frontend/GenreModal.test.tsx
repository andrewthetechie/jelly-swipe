import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import GenreModal from "./GenreModal"
import { renderWithRoom } from "./test/renderWithRoom"
import { mockFetch } from "./test/mockFetch"

function renderGenreModal() {
    const handleGendreClick = vi.fn()
    const handleGenreChange = vi.fn()

    const utils = renderWithRoom(
        <GenreModal 
            handleGenreClick={handleGendreClick}
            handleGenreChange={handleGenreChange}
        />,
        {
            currentRoomCode: "1234",
            genre: "All"
        }
    )

    return {
        ...utils,
        handleGendreClick,
        handleGenreChange,
    }
}

describe("GenreModal - data loading and caching", () => {
    it("renders fetched genres", () => {

    })

    it("uses sessionStorage instead of fetching", () => {

    })

    it("caches fetched genres", () => {
        
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