import React from "react"
import type { TrailerResponse } from "./types"
import { fetchTrailer, RoomApiError } from "./roomApi"

export type TrailerState = "idle" | "loading" | "playing" | "unavailable"

export default function useTrailer(mediaId: string) {
    const [trailerState, setTrailerState] = React.useState<TrailerState>("idle")
    const [trailerKey, setTrailerKey] = React.useState<string | null>(null)
    const trailerAbort = React.useRef<AbortController | null>(null)

    // Abort any in-flight trailer fetch when the caller unmounts (issue #339),
    // matching the pattern in useMovieCast.tsx:31.
    React.useEffect(() => {
        return () => {
            trailerAbort.current?.abort()
        }
    }, [])

    const loadTrailer = () => {
        if (trailerState !== "idle") return
        setTrailerState("loading")
        trailerAbort.current = new AbortController()
        fetchTrailer(mediaId, trailerAbort.current.signal)
            .then((data: TrailerResponse) => {
                setTrailerKey(data.youtube_key)
                setTrailerState("playing")
            })
            .catch((err) => {
                // Unmounting aborts the request; ignore that as a no-op rather
                // than flipping to "unavailable" on a component that is gone.
                if ((err as Error).name === "AbortError") return
                // A 404 is the expected "no trailer" answer, not an error.
                if (err instanceof RoomApiError && err.status === 404) {
                    setTrailerState("unavailable")
                    return
                }
                console.error("Error fetching trailer:", err)
                setTrailerState("unavailable")
            })
    }

    return {
        trailerState,
        trailerKey,
        loadTrailer,
    }
}
