# Features Research

**Domain:** Jellyfin as alternative to Plex for Kino Swipe  
**Researched:** 2026-04-22

## Table stakes (must work for “parity”)

- **Server session** — Authenticate application to Jellyfin; reuse access token for API calls.  
- **Movie library** — List or query items in the configured movies library; stable item IDs for swipes and matches.  
- **Posters / thumbs** — Resolve primary image URLs and serve via app proxy (browser should not need raw API tokens).  
- **Genres** — Enough genre metadata to reproduce “filter by genre” and “All” / random deck behavior.  
- **Recently added** — Time-based sort or filter equivalent to current Plex “Recently Added” mode.  
- **Item identity in API** — Fetch single item by ID for TMDB lookup chain (title/year) used by trailer and cast routes.

## Differentiators (nice, not required for v1)

- Jellyfin collections as extra filters.  
- Multiple libraries selectable via config.

## Anti-features (deliberately not building here)

- **Dual provider runtime** — One backend per instance only.  
- **Full Jellyfin UI replacement** — Read-only consumption for swipe deck.

## Dependencies between features

- Image proxy depends on auth token and item/image path model.  
- Genre filter depends on how genres are stored on Jellyfin items (strings vs provider IDs).

---
*Features research for Jellyfin milestone*
