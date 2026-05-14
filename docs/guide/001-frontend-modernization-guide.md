# Frontend Modernization Guide

This guide is for a new frontend contributor modernizing Jellyswipe's UI with React while preserving the app's current deployment model: one Docker container running the FastAPI backend and serving static frontend assets.

The goal is not to preserve the existing visual design. The goal is to preserve the product behavior: users can authenticate with Jellyfin, create or join a room, swipe left/right on media cards, get matches, and use the app as an installable phone-friendly PWA.

## Current Frontend

The current UI is a no-build static frontend:

- `jellyswipe/templates/index.html` renders the main page.
- `jellyswipe/static/app.js` contains browser-side behavior.
- `jellyswipe/static/styles.css` contains styling.
- `jellyswipe/static/manifest.json`, `jellyswipe/static/sw.js`, and icons provide PWA support.

FastAPI serves frontend files from:

- `/` via `jellyswipe/routers/static.py`.
- `/static/*` via the static file mount in `jellyswipe/__init__.py`.
- `/manifest.json`, `/sw.js`, and `/favicon.ico` via explicit static routes.

The Docker image currently copies the `jellyswipe/` package into the final image. The React production build must end up inside the package paths FastAPI serves. The final runtime container should remain Python/FastAPI plus built static files. Node should be build-time only.

## Product Behaviors To Preserve

The redesign can change layout, styling, component structure, and even UX details, but these core flows must keep working:

- Login using the server Jellyfin identity.
- Create a session with Movies, TV Shows, and Solo options.
- Join a hosted session with a pairing code.
- Support solo sessions and hosted two-user sessions from the start.
- Display a deck of media cards.
- Swipe left and right on cards.
- Provide accessible button alternatives for swipe actions.
- Show a match when both hosted users swipe right on the same item.
- Save solo right swipes as matches.
- Show current matches.
- Preserve mobile-first behavior so the app feels like a phone app.
- Preserve PWA install behavior from the start.

Secondary features can come after the first usable checkpoint:

- Match history management.
- Trailer playback.
- Cast display.
- Add to Jellyfin watchlist/favorites.
- Genre filter.
- Hide watched filter.
- Advanced visual polish.

## Backend Contract

Start with the existing API as-is. Use `/docs`, `/redoc`, and `/openapi.json` to learn the contract.

Important endpoints used by the current frontend include:

- `POST /auth/jellyfin-use-server-identity`
- `POST /auth/logout`
- `GET /me`
- `POST /room`
- `POST /room/{code}/join`
- `GET /room/{code}/deck`
- `POST /room/{code}/swipe`
- `POST /room/{code}/undo`
- `POST /room/{code}/quit`
- `GET /room/{code}/status`
- `GET /room/{code}/stream`
- `GET /matches`
- `POST /matches/delete`
- `GET /genres`
- `POST /room/{code}/genre`
- `POST /room/{code}/watched-filter`
- `GET /get-trailer/{media_id}`
- `GET /cast/{media_id}`
- `POST /watchlist/add`
- `GET /proxy?path=...`

Frontend API calls should use same-origin requests and preserve cookie-based sessions. Server-sent events should continue to use `EventSource`.

If an API endpoint is broken or blocks the React implementation, coordinate with the maintainer before changing backend behavior. API fixes should include backend tests.

## Do Not Change Without Coordination

Avoid changing these areas unless frontend work is blocked and the maintainer agrees:

- Backend service behavior in `jellyswipe/services/`.
- Database models in `jellyswipe/models/`.
- Repository behavior in `jellyswipe/repositories/`.
- Alembic migrations in `alembic/versions/`.
- Auth/session internals.
- Room matching/swipe transaction behavior.
- Docker runtime behavior.
- Public API response shapes.

Allowed frontend integration changes include:

- Adding frontend build tooling.
- Adding a `frontend/` directory.
- Adjusting static-serving so FastAPI serves the React production build.
- Updating PWA assets and metadata if installability remains intact.
- Replacing the old `index.html`, `app.js`, and `styles.css` after React reaches functional parity.

## Recommended Workflow

Use an integration feature branch for the project, then practice small PRs into that branch.

Suggested branches:

- Integration branch: `frontend/react-modernization`
- First PR branch: `frontend/react-scaffold`
- Later PR branches: `frontend/api-client`, `frontend/login-flow`, `frontend/session-setup`, `frontend/swipe-deck`, `frontend/matches`

PR expectations:

- Keep each PR focused on one learning milestone.
- Include screenshots or short screen recordings for UI changes.
- Explain what user flow now works.
- Explain what is intentionally not done yet.
- Run frontend tests locally before opening the PR.
- Let CI run the full backend/frontend lint and test suite.

Commit message examples:

- `feat(frontend): add React app scaffold`
- `feat(frontend): add typed API client`
- `feat(frontend): implement session setup screen`
- `test(frontend): cover room creation client`
- `docs(frontend): document local React dev workflow`

Merge the integration branch back to `main` only when it reaches a usable checkpoint. `main` should always deploy and function.

## First Usable Checkpoint

The first merge back to `main` should include the core app loop:

- React app is served by FastAPI in production mode.
- Docker still builds one deployable container.
- Login works.
- Hosted two-user sessions work.
- Solo sessions work.
- Users can create and join sessions.
- Deck cards render on mobile.
- Left and right swipe gestures work.
- Button alternatives for left/right swipes work.
- Matches display.
- PWA install behavior still works.

## Suggested React Stack

The final choices are part of the contributor's learning exercise. Document the choice and the tradeoffs in the PR.

Strong default path:

- Vite for frontend build tooling.
- React with TypeScript.
- Vitest for frontend unit tests.
- Testing Library for component tests.
- A dedicated `frontend/` directory.

Styling options:

- Plain CSS or CSS modules: easiest to understand and close to existing HTML/CSS knowledge.
- Tailwind CSS: good modern frontend practice if the contributor wants utility classes and design-token habits.
- Sass: reasonable if nested CSS and variables are desired.
- CSS-in-JS: probably unnecessary for the first version.

Interaction/data options:

- `@use-gesture/react`: useful for predictable swipe gestures across touch and pointer devices.
- TanStack Query: useful later if API loading/caching state gets repetitive.
- Zustand: useful later if local React state becomes difficult to pass around.
- React Router: skip initially; this should start as a single-screen app.
- OpenAPI type generation: useful later, but hand-write initial domain types so the data model is easy to learn.

Initial TypeScript types to hand-write:

- `MediaCard`
- `RoomStatus`
- `Match`
- `CurrentUser`
- `CreateRoomRequest`
- `CreateRoomResponse`
- `SwipeDirection`
- `SessionEvent`

## Development Modes

Use two development modes.

Fast local frontend iteration:

1. Run the FastAPI backend with `uv run python -m jellyswipe.bootstrap`.
2. Run the selected React dev server from `frontend/`.
3. Configure the React dev server to proxy API requests to FastAPI.
4. Keep API calls same-origin from the frontend perspective.

Production/static-serving validation:

1. Build the React app.
2. Emit or copy the generated `index.html` and hashed assets into backend-served package paths.
3. Run `uv run python -m jellyswipe.bootstrap`.
4. Open the FastAPI-served app, not the React dev server.
5. Confirm `/`, `/manifest.json`, `/sw.js`, icons, and static assets resolve.
6. Build the Docker image and confirm the one-container app still serves the UI and API together.

Use normal hashed production assets. Do not disable hashed filenames just to make static references easier.

## PWA Requirements

PWA behavior is required from the start.

Preserve or replace these intentionally:

- Mobile viewport behavior.
- `manifest.json`.
- App icons.
- `theme-color`.
- Service worker registration.
- `/sw.js` serving path.
- Installability on phones.

Initial bias: preserve the current simple `sw.js` until the React app is stable. A Vite PWA plugin can be evaluated later, but avoid adding caching complexity before the core app works.

## Accessibility Requirements

Build accessibility basics in from the start:

- Provide visible buttons for left and right actions.
- Do not make swipe gestures the only way to use the app.
- Use real `button` elements for actions.
- Use semantic headings and landmarks where practical.
- Ensure dialogs/modals are keyboard reachable.
- Preserve visible focus states.
- Use readable text contrast.
- Avoid tiny touch targets.
- Add useful alt text for meaningful images.

This does not need to be a full accessibility audit in the first PR, but avoid patterns that would require a major retrofit.

## Frontend Testing

Start with modest frontend tests.

Good first tests:

- API client handles successful login response.
- API client handles room creation response.
- API client sends boolean room setup payloads.
- Swipe state advances when a user swipes left or right.
- Match overlay renders when match data is present.
- Critical components render without crashing.

Local expectation:

- Run frontend tests before opening frontend PRs.

CI expectation:

- CI runs the full project linting and test suite on every PR.
- Before merging the integration branch to `main`, verify frontend tests, production frontend build, backend tests, and Docker/static-serving behavior.

## First Week Plan

Day 1: Run and inspect the existing app.

- Set up the backend with `uv sync`.
- Add local `.env` values from the maintainer.
- Run `uv run python -m jellyswipe.bootstrap`.
- Use the current UI on a phone-sized viewport.
- Write down the main screens and flows.

Day 2: Learn the API contract.

- Open `/docs`, `/redoc`, and `/openapi.json`.
- Map each UI flow to backend endpoints.
- Hand-write initial TypeScript domain type drafts.
- Ask the maintainer about any confusing response shape.

Day 3: Choose frontend tooling.

- Compare Vite, styling options, test tools, and gesture options.
- Document the selected stack and why.
- Create the first small branch, for example `frontend/react-scaffold`.

Day 4: Scaffold React.

- Add `frontend/`.
- Add React with TypeScript.
- Add the first test command.
- Render a simple app shell.
- Open a PR into `frontend/react-modernization`.

Day 5: Connect the shell to the backend.

- Add a small typed API client.
- Call `/me` or login endpoint.
- Show authenticated/unauthenticated UI state.
- Add tests for the API client.

## Milestone Roadmap

Milestone 1: React scaffold.

Acceptance criteria:

- `frontend/` exists with React and TypeScript.
- A frontend test command exists.
- React renders a simple app shell.
- The chosen tooling is documented.
- No backend behavior changes.

Milestone 2: Static-serving integration.

Acceptance criteria:

- Production build emits hashed assets.
- FastAPI serves the built React app.
- `/manifest.json`, `/sw.js`, favicon, and icons still resolve.
- Docker still produces one container.

Milestone 3: API client and session state.

Acceptance criteria:

- Typed API client exists.
- Login/logout/current-user flow works.
- API errors have basic UI handling.
- Frontend tests cover at least one success and one failure path.

Milestone 4: Session setup.

Acceptance criteria:

- User can create hosted sessions.
- User can create solo sessions.
- User can join a hosted session by code.
- Movies and TV Shows options send JSON booleans.
- Mobile layout is usable.

Milestone 5: Deck and swipe.

Acceptance criteria:

- Deck cards render from `GET /room/{code}/deck`.
- Swipe left/right calls `POST /room/{code}/swipe`.
- Button alternatives call the same behavior.
- Touch interaction works on a phone-sized viewport.
- Basic loading and empty states exist.

Milestone 6: Realtime and matches.

Acceptance criteria:

- `EventSource` connects to `GET /room/{code}/stream`.
- Hosted two-user updates work.
- Match display works.
- Solo right-swipes create visible matches.
- Disconnect/reload has basic recovery behavior.

Milestone 7: Replace old frontend.

Acceptance criteria:

- React reaches the first usable checkpoint.
- Old static frontend files are removed or no longer used.
- Project screenshots are updated.
- Production static-serving path is tested.
- Integration branch can merge back to `main`.

## Manual Smoke Checklist

Before the first merge back to `main`, test:

- Fresh page load.
- Login.
- Logout.
- Create hosted session.
- Join hosted session in a second browser/device.
- Swipe left.
- Swipe right.
- Match appears when both users swipe right.
- Solo session creates matches.
- Refresh during active room.
- Open matches.
- End session.
- Install/open as PWA on a phone if possible.
- Docker image serves the React UI and API from the same container.

## Learning Goals

This project should teach:

- How to enter an existing open-source codebase.
- How to preserve backend contracts while replacing frontend implementation.
- How to make small reviewable PRs.
- How to write useful commit messages.
- How to use TypeScript to model API data.
- How to test frontend behavior.
- How to integrate a frontend build into a backend-served app.
- How to keep mobile/PWA requirements visible during development.
