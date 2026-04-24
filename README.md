# Jelly-Swipe

[![GitHub](https://img.shields.io/github/stars/AndrewTheTechie/jelly-swipe?style=social)](https://github.com/AndrewTheTechie/jelly-swipe)

**Fork:** This project was forked from [Bergasha/kino-swipe](https://github.com/Bergasha/kino-swipe) to add Jellyfin support. It is maintained by [@AndrewTheTechie](https://github.com/AndrewTheTechie).

Always trying to decide on a movie to watch together?, This may be the fun solution you've been looking for.
Dating app style swipe right for like swipe left for nope, If you both swipe right on the 
same movie, IT'S A MATCH!!



## Screenshots
<img width="320" height="640" alt="1" src="https://github.com/user-attachments/assets/4517d22b-aba7-419f-8fc1-19cf5b93af8d" />
<img width="320" height="640" alt="2" src="https://github.com/user-attachments/assets/d23fad4e-6f39-4ba8-9840-d1c8b745cd38" />
<img width="320" height="640" alt="3" src="https://github.com/user-attachments/assets/f95ae259-8a1d-4021-a344-ea0dc288f905" />
<img width="320" height="640" alt="4" src="https://github.com/user-attachments/assets/3dea1bdc-3bb4-43aa-879d-ae5b6b85b6ef" />
<img width="320" height="640" alt="5" src="https://github.com/user-attachments/assets/3f1199eb-c21e-405c-8b27-7323585efe5c" />


<div align="center">
  <video src="https://github.com/user-attachments/assets/37a2a485-ef1f-4c45-9eea-7a858323e01a" 
    width="750" 
    autoplay 
    loop 
    muted 
    playsinline>
  </video>
</div>




## Features
- **Plex Integration:** Connects directly to your server to pull random movies.
- **Real-Time Sync:** Host a room, share a 4-digit code, and swipe with a partner instantly.
- **Visual Feedback:** Faint Red/Green "glow" overlays that react as you drag the posters left or right.
- **Select Genre:** Both sessions will stay in sync while browsing genres.
- **Add to watchlist:** Tap on each match and either open in Plex or add to watchlist for later.
- **Watch trailer** Tap on the main poster in swipedeck for full synopsis and even watch the trailer. 
- **PWA Support:** Add it to your Home Screen for a native app feel.
- **Match Notifications:** Instant alerts when you both swipe right on the same movie.
- **Match History** All matches now live in Match History until you're ready to delete them.
- **Solo Mode** Flying solo? no worries, just host session and flick the solo toggle. (Every right swipe saves to Match History) 

## Media backend (Plex or Jellyfin)

Each deployment uses **exactly one** media backend, selected with `MEDIA_PROVIDER`:

- `plex` (default if unset) — today’s Plex integration.
- `jellyfin` — Jellyfin-oriented configuration. **Phase 3+:** env vars are validated at import (Phase 1); the **first** `get_provider()` use in jellyfin mode obtains a server access token (API key or username/password) and verifies a minimal authenticated **`/Items`** call. **Phase 4+:** deck, genres, `/proxy` thumbs (`jellyfin/{itemId}/Primary`), TMDB routes, and `/plex/server-info` JSON parity are implemented behind `JellyfinLibraryProvider`. Target **Jellyfin 10.8+** unless you pin an older server—call out version quirks in ops notes if you diverge.

**Two instances rule:** Plex and Jellyfin are **not** supported in a single process. If you need both, run **two instances** (two containers or two hosts), each with its own database volume and `MEDIA_PROVIDER`.

### Upgrade note (Kino Swipe → Jelly Swipe)

- **Plex.tv:** The in-app Plex client identifier changed. If you used Plex pin login before, you may need to sign in again once.
- **Database file:** The default SQLite file is now `data/jellyswipe.db`. To keep an existing database from Kino Swipe, either copy `data/kinoswipe.db` to `data/jellyswipe.db` or set `DB_PATH` to your old file.

### Environment variables

| Variable | Required when | Description |
|----------|-----------------|-------------|
| `MEDIA_PROVIDER` | Optional | `plex` (default) or `jellyfin` (case-insensitive). |
| `FLASK_SECRET` | Always | Flask session secret. |
| `TMDB_API_KEY` | Always | TMDB API key (trailers / cast). |
| `PLEX_URL` | Plex only | Base URL of your Plex server (no trailing slash). |
| `PLEX_TOKEN` | Plex only | Server admin token for library access. |
| `JELLYFIN_URL` | Jellyfin only | Base URL of your Jellyfin server (no trailing slash). |
| `JELLYFIN_API_KEY` | Jellyfin (one of two auth bundles) | API key for unattended server access. |
| `JELLYFIN_USERNAME` | Jellyfin (with password, if no API key) | Account username for Jellyfin. |
| `JELLYFIN_PASSWORD` | Jellyfin (with username, if no API key) | Account password for Jellyfin. |
| `JELLYFIN_DEVICE_ID` | Optional (Jellyfin) | Stable device id string sent with Jellyfin auth headers (default is built-in). |

### Jellyfin user identity contract (Phase 5)

In Jellyfin mode, this app keeps the legacy `plex_id` DB column name for compatibility, but
stores **Jellyfin user IDs** in that field. Requests can include either:

- `X-Provider-User-Id` (preferred neutral header), or
- `X-Plex-User-ID` (legacy compatibility header),

and for user-scoped list actions must include a Jellyfin user token via:

- `Authorization: MediaBrowser ... Token=\"<user-token>\"` (preferred), or
- `X-Plex-Token` (legacy compatibility path).

### Jellyfin operator checks (manual)

1. **Happy path:** With valid `JELLYFIN_URL` and credentials, start the app and hit provider endpoints (`/genres`, `/movies`, `/plex/server-info`). Confirm logs show **no** API keys or access tokens.  
2. **Re-login / reset:** Revoke the API key or set a wrong password, restart or trigger a code path that calls `reset()` on the provider (same spirit as Plex connection recovery), restore valid credentials, and confirm authenticated **`/Items`** succeeds again (Phase 3 success criterion).
3. **After recovery:** Restart the process (or rely on the next provider use after `reset()`) and hit `/genres` or create/join a room so `get_provider()` re-authenticates — you should be back to a working deck without pasting any tokens into logs or tickets.

### Minimal `.env` examples

**Plex mode**

```env
MEDIA_PROVIDER=plex
PLEX_URL=https://your-plex-host:32400
PLEX_TOKEN=your-plex-token-here
TMDB_API_KEY=your-tmdb-v3-key
FLASK_SECRET=long-random-string
```

**Jellyfin mode** (library deck/UI parity is Phase 4; auth + token in Phase 3)

```env
MEDIA_PROVIDER=jellyfin
JELLYFIN_URL=http://your-jellyfin-host:8096
JELLYFIN_API_KEY=your-jellyfin-api-key
TMDB_API_KEY=your-tmdb-v3-key
FLASK_SECRET=long-random-string
```

## Coming Soon
~~Match History: Match history folder accessible outside session for easy access.~~   
  

## Requirements
- **Media backend:** Plex or Jellyfin — see [Media backend (Plex or Jellyfin)](#media-backend-plex-or-jellyfin) and the env table above.
- **TMDB API key** — required at startup (trailers/cast); keep the key private.
- **HTTPS/Reverse Proxy:** To "Install" the app as a PWA on your phone so it looks like an app, you must access it over an HTTPS connection. If you access it over local ip, it will work in the browser but when added to homescreen it will just act as a shortcut not like an app.

## TMDB API instructions
Only required if you want trailers to work on the rear of the movie posters.

1. Create a free TMDB Account
If you don't already have one, you need to register on the TMDB website:

Go to themoviedb.org/signup.

Verify your email address to activate the account.

2. Access the API Settings
Once logged in:

Click on your Profile Icon in the top right corner of the screen.

Select Settings from the dropdown menu.

On the left-hand sidebar, click on API.

3. Create an API Key
Under the "Request an API Key" section, click on the link for Create.

You will be asked to choose a type of API key. Select Developer.

Accept the Terms of Use.

Fill out the form: * Type of Use: Personal/Educational.

Application Name: Jelly-Swipe.

Application URL: (You can put localhost or your server's IP).

Application Summary: "An app to help find movies to watch from my Plex library with a Tinder-style swipe interface."

Submit the form.

4. Copy your API Key
You will now see two different keys. For Jelly-Swipe, you need the API Key (v3 auth). It is a long string of numbers and letters.
---

## Deployment

### Option 1: Docker (Recommended)
Copy and paste this into your terminal. Replace the variables with your specific setup.

```bash
services:
  jelly-swipe:
    image: andrewthetechie/jelly-swipe:latest
    container_name: jelly-swipe
    ports:
      - "5005:5005"
    environment:
      - PLEX_URL=https://YOUR_PLEX_IP:32400
      - PLEX_TOKEN=YOUR_PLEX_TOKEN
      - FLASK_SECRET=SomeRandomString
      - TMDB_API_KEY=your_copied_tmdb_key_here
    volumes:
      - ./data:/app/data
      - ./static:/app/static
    restart: unless-stopped
```

**Option 2 — Docker Run**
```bash
docker run -d \
  --name jelly-swipe \
  -p 5005:5005 \
  -e PLEX_URL=https://YOUR_PLEX_IP:32400 \
  -e PLEX_TOKEN=YOUR_PLEX_TOKEN \
  -e FLASK_SECRET=SomeRandomString \
  -e TMDB_API_KEY=your_copied_tmdb_key_here \
  -v ./data:/app/data \
  -v ./static:/app/static \
  --restart unless-stopped \
  andrewthetechie/jelly-swipe:latest
```

<img src="https://github.com/user-attachments/assets/97e2c08b-5421-4f16-a798-acca2bb76a60" width="100"/>

"This product uses the TMDB API but is not endorsed or certified by TMDB."
