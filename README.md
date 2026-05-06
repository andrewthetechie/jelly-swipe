# Jelly-Swipe

[![GitHub](https://img.shields.io/github/stars/AndrewTheTechie/jelly-swipe?style=social)](https://github.com/AndrewTheTechie/jelly-swipe)

**Fork:** This project was forked from [Bergasha/kino-swipe](https://github.com/Bergasha/kino-swipe). It is maintained by [@AndrewTheTechie](https://github.com/AndrewTheTechie).

Always trying to decide on a movie to watch together?, This may be the fun solution you've been looking for.
Dating app style swipe right for like swipe left for nope, If you both swipe right on the 
same movie, IT'S A MATCH!!

## Screenshots
<details>
<summary>Click to expand screenshots</summary>

<br>

<img src="screenshots/main_page.png" alt="Main App Screen" width="320" height="640" />
<img src="screenshots/host_session.png" alt="Host Session Screen" width="320" height="640" />
<img src="screenshots/view_movie.png" alt="View Movie Screen" width="320" height="640" />
<img src="screenshots/view_movie_2.png" alt="View Movie Details" width="320" height="640" />
<img src="screenshots/match_movie.png" alt="Make a Match" width="320" height="640" />

</details>

## Features
- **Jellyfin Integration:** Connects directly to your server to pull random movies.
- **Real-Time Sync:** Host a room, share a 4-digit code, and swipe with a partner instantly.
- **Visual Feedback:** Faint Red/Green "glow" overlays that react as you drag the posters left or right.
- **Select Genre:** Both sessions will stay in sync while browsing genres.
- **Add to watchlist:** Tap on each match and either open in Jellyfin or add to watchlist for later.
- **Watch trailer** Tap on the main poster in swipedeck for full synopsis and even watch the trailer.
- **PWA Support:** Add it to your Home Screen for a native app feel.
- **Match Notifications:** Instant alerts when you both swipe right on the same movie.
- **Match History** All matches now live in Match History until you're ready to delete them.
- **Solo Mode** Flying solo? no worries, just host session and flick the solo toggle. (Every right swipe saves to Match History) 

## Media backend: Jellyfin

This application connects directly to a **Jellyfin** server to pull random movies from your library. Target **Jellyfin 10.8+** unless you pin an older server—call out version quirks in ops notes if you diverge.

### Environment variables

| Variable | Required when | Description |
|----------|-----------------|-------------|
| `FLASK_SECRET` | Always | Flask session secret. |
| `TMDB_API_KEY` | Always | TMDB API key (trailers / cast). |
| `JELLYFIN_URL` | Always | Base URL of your Jellyfin server (no trailing slash). |
| `JELLYFIN_API_KEY` | With API key | API key for unattended server access. |
| `JELLYFIN_USERNAME` | With password (if no API key) | Account username for Jellyfin. |
| `JELLYFIN_PASSWORD` | With username (if no API key) | Account password for Jellyfin. |
| `JELLYFIN_DEVICE_ID` | Optional | Stable device id string sent with Jellyfin auth headers (default is built-in). |

### Jellyfin user identity contract

This app stores **Jellyfin user IDs** in the database user_id field. Requests can include the user identity via:

- `X-Provider-User-Id` (preferred neutral header), or
- `X-Jellyfin-User-Id` (Jellyfin-specific header),

and for user-scoped list actions must include a Jellyfin user token via:

- `Authorization: MediaBrowser ... Token=\"<user-token>\"` (preferred), or
- `X-Emby-Token` (alternative header).

### Jellyfin operator checks (manual)

1. **Happy path:** With valid `JELLYFIN_URL` and credentials, start the app and hit provider endpoints (`/genres`, `/movies`, `/jellyfin/server-info`). Confirm logs show **no** API keys or access tokens.
2. **Re-login / reset:** Revoke the API key or set a wrong password, restart or trigger a code path that calls `reset()` on the provider, restore valid credentials, and confirm authenticated **`/Items`** succeeds again.
3. **After recovery:** Restart the process (or rely on the next provider use after `reset()`) and hit `/genres` or create/join a room so `get_provider()` re-authenticates — you should be back to a working deck without pasting any tokens into logs or tickets.

### Minimal `.env` example

```env
JELLYFIN_URL=http://your-jellyfin-host:8096
JELLYFIN_API_KEY=your-jellyfin-api-key
TMDB_ACCESS_TOKEN=your-tmdb-read-access-token
FLASK_SECRET=long-random-string
```

Alternatively, use username/password authentication instead of API key:

```env
JELLYFIN_URL=http://your-jellyfin-host:8096
JELLYFIN_USERNAME=your-username
JELLYFIN_PASSWORD=your-password
TMDB_ACCESS_TOKEN=your-tmdb-read-access-token
FLASK_SECRET=long-random-string
```

## Requirements
- **Media backend:** Jellyfin — see [Media backend: Jellyfin](#media-backend-jellyfin) and the env table above.
- **TMDB Read Access Token** — required at startup (trailers/cast); keep the token private.
- **HTTPS/Reverse Proxy:** To "Install" the app as a PWA on your phone so it looks like an app, you must access it over an HTTPS connection. If you access it over local ip, it will work in the browser but when added to homescreen it will just act as a shortcut not like an app.

## TMDB API instructions
Only required if you want trailers to work on the rear of the movie posters.

1. Go to https://www.themoviedb.org/settings/api
2. Log in or create a free TMDB account
3. Under the **API** section, find **Read Access Token** (this is the v4 Bearer token)
4. Copy the token value (not the API key)
5. Set as `TMDB_ACCESS_TOKEN` environment variable

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
      - JELLYFIN_URL=http://YOUR_JELLYFIN_IP:8096
      - JELLYFIN_API_KEY=your-jellyfin-api-key
      - FLASK_SECRET=SomeRandomString
      - TMDB_ACCESS_TOKEN=your_copied_tmdb_token_here
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
  -e JELLYFIN_URL=http://YOUR_JELLYFIN_IP:8096 \
  -e JELLYFIN_API_KEY=your-jellyfin-api-key \
  -e FLASK_SECRET=SomeRandomString \
  -e TMDB_ACCESS_TOKEN=your_copied_tmdb_token_here \
  -v ./data:/app/data \
  -v ./static:/app/static \
  --restart unless-stopped \
  andrewthetechie/jelly-swipe:latest
```

### Unraid Template

For Unraid users, a pre-configured template is provided at `unraid_template/jelly-swipe.html`. This template uses Jellyfin API key authentication and requires the following environment variables:

- **JELLYFIN_URL** — Base URL of your Jellyfin server (no trailing slash)
- **JELLYFIN_API_KEY** — API key for unattended server access
- **TMDB_ACCESS_TOKEN** — TMDB Read Access Token for trailers and cast information
- **FLASK_SECRET** — Random secret string for Flask session security

All fields are blank by default and must be filled in by the user. The template does not expose username/password authentication options — it uses API key authentication only.

**CI Validation:** The Unraid template is automatically validated by a GitHub Actions workflow (`.github/workflows/unraid-template-lint.yml`) that ensures all template variables are a recognized subset of the application's environment variables. This prevents template drift and maintains consistency between the template and the application code.

<img src="https://github.com/user-attachments/assets/97e2c08b-5421-4f16-a798-acca2bb76a60" width="100"/>

## Development

For local development and contributing, use **uv** for dependency management. This project requires **Python 3.13**.

### First-time setup

```bash
# Install dependencies from the committed lockfile
uv sync
```

This creates a virtual environment in `.venv/` and installs all dependencies from `pyproject.toml` and `uv.lock`.

### Running the app locally

**Development server (auto-reload):**
```bash
uv run python -m jellyswipe.bootstrap
```

**Production-style server (for testing):**
```bash
uv run python -m jellyswipe.bootstrap
```

### Managing dependencies

**Add a new dependency:**
```bash
uv add <package-name>
```

**Update the lockfile after dependency changes:**
```bash
uv lock --upgrade
```

Commit both `pyproject.toml` and `uv.lock` when adding or updating dependencies.

### Notes

- The app is installed as a package (`jellyswipe/` layout), not a script. Run it via `uv run python -m jellyswipe.bootstrap`.
- All production deployment uses Docker (see Deployment section above). Local dev uses uv for fast iteration.
- Distribution is Docker-only (Docker Hub and GHCR). There is no PyPI package to install via pip.

"This product uses the TMDB API but is not endorsed or certified by TMDB."
