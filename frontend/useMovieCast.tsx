import React from "react"
import { CastMember } from "./types"
import { CastResponse } from "./types"
import { apiFetch } from "./api"

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
                const res: Response = await apiFetch(`/cast/${mediaId}`, {
                    method: 'GET',
                    headers: {'Content-Type': 'application/json'},
                    signal: controller.signal,
                })
                if (!res.ok) {
                    throw new Error(`Error fetching cast: ${res.status} ${res.statusText}`)
                }

                const data: CastResponse = await res.json()
                setCast(data.cast)
            } catch (err) {
                if ((err as Error).name === "AbordError") return
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