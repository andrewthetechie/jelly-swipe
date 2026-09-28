import { render, screen } from "@testing-library/react"
import MediaFacts from "./MediaFacts"

const defaultClassNames = {
    scoreClassName: "card-item-score",
    runtimeClassName: "card-item-runtime",
    yearClassName: "card-item-year",
}

describe("MediaFacts", () => {
    it("renders all three pills when rating, duration and year are present", () => {
        render(<MediaFacts rating={9.25} duration="52 min" year={2026} {...defaultClassNames} />)
        expect(screen.getByText("IMDb 9.25")).toBeInTheDocument()
        expect(screen.getByText("52 min")).toBeInTheDocument()
        expect(screen.getByText("2026")).toBeInTheDocument()
    })

    it("renders 'IMDb 0.00' for a zero rating", () => {
        render(<MediaFacts rating={0} duration="52 min" year={2026} {...defaultClassNames} />)
        expect(screen.getByText("IMDb 0.00")).toBeInTheDocument()
    })

    it("omits the rating pill when rating is null", () => {
        render(<MediaFacts rating={null} duration="52 min" year={2026} {...defaultClassNames} />)
        expect(screen.queryByText(/IMDb/)).not.toBeInTheDocument()
    })

    it("omits the year pill when year is null", () => {
        render(<MediaFacts rating={8} duration="52 min" year={null} {...defaultClassNames} />)
        expect(screen.queryByText("2026")).not.toBeInTheDocument()
    })

    it("omits the duration pill when duration is empty", () => {
        render(<MediaFacts rating={8} duration="" year={2026} {...defaultClassNames} />)
        expect(screen.queryByText("52 min")).not.toBeInTheDocument()
    })

    it("omits the duration pill when duration is null", () => {
        render(<MediaFacts rating={8} duration={null} year={2026} {...defaultClassNames} />)
        expect(screen.queryByText("52 min")).not.toBeInTheDocument()
    })

    it("applies caller-supplied class names to each pill", () => {
        render(
            <MediaFacts
                rating={8}
                duration="1h"
                year={2026}
                scoreClassName="match-list-score"
                runtimeClassName="match-list-runtime"
                yearClassName="match-list-year"
            />
        )
        expect(screen.getByText("IMDb 8.00")).toHaveClass("match-list-score")
        expect(screen.getByText("1h")).toHaveClass("match-list-runtime")
        expect(screen.getByText("2026")).toHaveClass("match-list-year")
    })
})
