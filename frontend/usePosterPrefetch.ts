import React from "react"

/**
 * Warm the poster URLs of upcoming deck cards so they're already in the browser
 * cache by the time those cards reach the top of the deck (issue #350). Pure
 * side effect: no state, no re-renders, nothing returned.
 *
 * The deck shrinks by one per swipe, so the effect re-runs with a new array on
 * each render; URLs already warmed during the hook's lifetime are tracked in a
 * ref Set so they are never re-requested.
 */
export const usePosterPrefetch = (urls: Array<string | null | undefined>): void => {
    const warmedRef = React.useRef<Set<string>>(new Set())

    React.useEffect(() => {
        for (const url of urls) {
            if (!url) continue
            if (warmedRef.current.has(url)) continue
            warmedRef.current.add(url)
            const img = new Image()
            img.decoding = "async"
            img.src = url
        }
    }, [urls])
}
