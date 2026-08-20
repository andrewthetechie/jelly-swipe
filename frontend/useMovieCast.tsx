import React from "react"
import type { CastMember } from "./types"
import type { CastResponse } from "./types"
import { fetchCast } from "./roomApi"

export default function useMovieCast(mediaId: string) {
    const [cast, setCast] = React.useState<CastMember[]>([])
    const [isLoading, setIsLoading] = React.useState<boolean>(false)
    const [error, setError] = React.useState<string | null>(null)

    React.useEffect(() => {
        const controller = new AbortController()

        async function run() {
            setIsLoading(true)
            setError(null)

            try {
                const data: CastResponse = await fetchCast(mediaId, controller.signal)
                setCast(data.cast)
            } catch (err) {
                if ((err as Error).name === "AbortError") return
                console.error("Error fetching cast:", err)
                setError("Error fetching cast")
            } finally {
                if (!controller.signal.aborted) setIsLoading(false)
            }
        }
        
        run()
        return () => controller.abort()
        
    }, [mediaId])

    return {
        cast,
        isLoading,
        error,
    }
}