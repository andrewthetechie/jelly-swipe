import { useState } from "react"
import sadLogo from "./assets/sad.png"
import type { ImgHTMLAttributes, JSX } from "react"

interface PosterImageProps {
    posterUrl: string | null | undefined
    alt: string
    className?: string
    draggable?: boolean
    showNoPosterLabel?: boolean
    /** Opt-in reserved frame (issue #350): wraps the img in a stable 2:3 box
     * with a navy placeholder and a fade-in on load, and renders the no-poster
     * fallback inside that box. Only the swipe card (CardItemView) sets this;
     * the match-modal call sites render a bare img exactly as before. */
    frame?: boolean
    /** Marks the top card so its poster loads with fetchpriority="high". */
    priority?: boolean
}

type LoadState = "loading" | "loaded" | "failed"

export default function PosterImage({
    posterUrl,
    alt,
    className,
    draggable,
    showNoPosterLabel = false,
    frame = false,
    priority = false,
}: PosterImageProps): JSX.Element {
    // Loading state machine: loading → loaded (onLoad: fade the poster in over
    // the placeholder) or → failed (onError: the null-poster treatment).
    const [loadState, setLoadState] = useState<LoadState>("loading")
    // Reset the state machine whenever posterUrl changes so a recycled frame
    // doesn't keep the previous poster's fade/error state (deck cards are keyed
    // by mediaId, but guard anyway).
    const [currentUrl, setCurrentUrl] = useState(posterUrl)
    if (currentUrl !== posterUrl) {
        setCurrentUrl(posterUrl)
        setLoadState("loading")
    }

    const posterFailed = loadState === "failed"
    const noPoster = !posterUrl || posterFailed
    const src = noPoster ? sadLogo : posterUrl

    const handleLoad = () => {
        // After a failure the src switches to the bundled fallback, whose own
        // load event must not flip us back to the broken poster URL.
        if (loadState === "failed") return
        setLoadState("loaded")
    }
    const handleError = () => setLoadState("failed")

    const frameLoaded = noPoster || loadState === "loaded"

    // The project's @types/react exposes `fetchPriority`, but the React 18.3.1
    // runtime doesn't recognise the camelCase prop (it warns and drops it), so
    // pass the lowercase `fetchpriority` attribute through a typed cast — the
    // rendered DOM attribute stays readable as `fetchpriority`.
    const imgProps: ImgHTMLAttributes<HTMLImageElement> & { fetchpriority?: string } = {
        src,
        alt,
        className,
        draggable,
        decoding: "async",
        onLoad: handleLoad,
        onError: handleError,
    }
    if (priority) {
        imgProps.fetchpriority = "high"
    }
    const img = <img {...imgProps} />

    if (!frame) {
        return (
            <>
                {img}
                {showNoPosterLabel && noPoster && (
                    <div className="no-poster">No poster available</div>
                )}
            </>
        )
    }

    return (
        <div className={`poster-frame ${frameLoaded ? "poster-frame-loaded" : ""}`}>
            {img}
            {showNoPosterLabel && noPoster && (
                <div className="no-poster">No poster available</div>
            )}
        </div>
    )
}
