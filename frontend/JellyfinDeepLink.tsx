import type { JSX } from "react"

interface JellyfinDeepLinkProps {
    deepLink: string | null
    className: string
    linkClassName: string
}

export default function JellyfinDeepLink({
    deepLink,
    className,
    linkClassName,
}: JellyfinDeepLinkProps): JSX.Element {
    if (deepLink) {
        return (
            <a href={deepLink} target="_blank" rel="noopener noreferrer" className={linkClassName}>
                Open in Jellyfin 🍿
            </a>
        )
    }
    return (
        <button type="button" className={className} disabled>
            Open in Jellyfin 🍿
        </button>
    )
}
