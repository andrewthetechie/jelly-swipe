import React from "react"
import { CastMember } from "./types"
import { CastResponse } from "./types"
import { apiFetch } from "./api"

export default function useMovieCast(mediaId: string) {
    const [cast, setCast] = React.useState<CastMember[]>([])
    const [isLoading, setIsLoading] = React.useState<boolean>(false)
    const [error, setError] = React.useState<string | null>(null)

    const getCast = React.useCallback(async () => {
        setIsLoading(true)
        setError(null)

        try {
            const res: Response = await apiFetch(`/cast/${mediaId}`, {
                method: 'GET',
                headers: {'Content-Type': 'application/json'},
            })
            if (!res.ok) {
                throw new Error(`Error fetching cast: ${res.status} ${res.statusText}`)
            }

            const data: CastResponse = await res.json()
            setCast(data.cast)
        } catch (err) {
            console.error("Error fetching cast:", err)
            setError("Error fetching cast")
        } finally {
            setIsLoading(false)
        }
    }, [mediaId])

    React.useEffect(() => {
        void getCast() 
    }, [getCast])

    return {
        cast,
        isLoading,
        error,
    }
}