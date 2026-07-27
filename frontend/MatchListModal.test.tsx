import { screen, render } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import MatchListModal from "./MatchListModal"
import { makeMatchList } from "./test/fixtures"

describe("MatchListModal - Match List Fetch", () => {
    it("successful GET renders match list", async () => {

    })

    it("failed GET leaves list empty", async () => {

    })

    it("GET sends the correct endpoint and method", async () => {

    })
})

describe("MatchListModal - rendering", () => {
    it("renders match metadata correctly", () => {

    })

    it("Keep Swiping button calls handleMatchListClick", () => {

    })

    it("omits option rating/runtime when missing from data", () => {

    })
})