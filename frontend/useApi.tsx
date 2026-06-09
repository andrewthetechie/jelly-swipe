import React from "react"
import { postJson } from "./api"

export interface UseApiResult<T = unknown> {
    data: T | null
    error: Error | null
    isLoading: boolean
    post: (path: string, body: unknown, options?: RequestInit) => Promise<T | null>
}

export function useApi<T = unknown>(): UseApiResult<T> {
    const [data, setData] = React.useState<T | null>(null)
    const [error, setError] = React.useState<Error | null>(null)
    const [isLoading, setIsLoading] = React.useState<boolean>(false)

    const post = React.useCallback(
        async (path: string, body: unknown, options: RequestInit = {}) => {
            setIsLoading(true)
            setError(null)

            try {
                const res = await postJson(path, body, options)
                if (!res.ok) {
                    const err = new Error(`Error posting to ${path}: ${res.status} ${res.statusText}`)
                    setError(err)
                    return null
                }

                const json = (await res.json()) as T
                setData(json)
                return json
            } catch (err) {
                const normalizedError = err instanceof Error ? err : new Error(String(err))
                setError(normalizedError)
                return null
            } finally {
                setIsLoading(false)
            }
        },
        [],
    )

    return {
        data,
        error,
        isLoading,
        post,
    }
}
