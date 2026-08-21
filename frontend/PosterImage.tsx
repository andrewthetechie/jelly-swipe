import sadLogo from "./assets/sad.png"
import type { JSX } from "react"

interface PosterImageProps {
    posterUrl: string | null | undefined
    alt: string
    className?: string
    draggable?: boolean
    showNoPosterLabel?: boolean
}

export default function PosterImage({
    posterUrl,
    alt,
    className,
    draggable,
    showNoPosterLabel = false,
}: PosterImageProps): JSX.Element {
    return (
        <>
            <img src={posterUrl ?? sadLogo} alt={alt} className={className} draggable={draggable} />
            {showNoPosterLabel && !posterUrl && (
                <div className="no-poster">No poster available</div>
            )}
        </>
    )
}