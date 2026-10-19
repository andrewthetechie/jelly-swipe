import type { JSX } from "react"
import { formatRating } from "./format"

interface MediaFactsProps {
    rating?: number | null
    duration?: string | null
    year?: number | null
    scoreClassName: string
    runtimeClassName: string
    yearClassName: string
}

export default function MediaFacts({
    rating,
    duration,
    year,
    scoreClassName,
    runtimeClassName,
    yearClassName,
}: MediaFactsProps): JSX.Element {
    return (
        <>
            {rating !== null && rating !== undefined && <div className={scoreClassName}>IMDb {formatRating(rating)}</div>}
            {duration && <div className={runtimeClassName}>{duration}</div>}
            {year !== null && year !== undefined && <div className={yearClassName}>{year}</div>}
        </>
    )
}
