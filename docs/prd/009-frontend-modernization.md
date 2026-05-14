# PRD: Frontend Modernization

## Problem Statement

Jellyswipe's current browser UI is a static HTML/CSS/JavaScript frontend. It works,
but it is difficult for a new frontend contributor to approach as a modern open
source frontend project. The app has meaningful product behavior — delegate
login, hosted rooms, solo mode, mobile swiping, realtime matches, match history,
PWA installation, Jellyfin artwork, trailers, cast, and watchlist actions — but
that behavior is concentrated in a monolithic browser script and tightly coupled
DOM manipulation.

The maintainer wants a new contributor who knows React, HTML, and CSS to practice
real open-source contribution habits while modernizing the UI. The contributor
should be able to make small PRs, learn the existing API contract, build a typed
frontend, test frontend behavior, document tradeoffs, and eventually replace the
old UI without breaking Jellyswipe's deployment contract.

The deployment contract is load-bearing: Jellyswipe must continue to ship as a
single Docker container that runs the FastAPI backend and serves the frontend as
static content alongside the API. The modernization must not turn the app into
two runtime services, require a Node process in production, or make `main`
undeployable while the frontend is being rebuilt.

## Solution

Build an incremental React and TypeScript frontend that fully replaces the
existing static UI once it reaches a usable checkpoint. The contributor will work
through small PRs into a frontend integration branch, then the integration branch
will merge back to `main` only when the app can still be used end-to-end.

The first usable checkpoint is the core app loop:

- React app is served by FastAPI in production mode.
- Docker still builds one deployable container.
- Delegate login works.
- Hosted two-user sessions work.
- Solo sessions work.
- Users can create and join rooms.
- Deck cards render on mobile.
- Left and right swipe gestures work.
- Accessible button alternatives for left/right decisions work.
- Matches display.
- PWA install behavior still works.

The contributor may redesign the visual style and UX as long as the app remains
mobile-first, PWA-friendly, and functionally complete. The implementation should
start from the existing API as-is, use same-origin cookie-authenticated requests,
continue using server-sent events for realtime room updates, and coordinate with
the maintainer before making backend/API changes.

## User Stories

1. As a new frontend contributor, I want a clear modernization goal, so that I can work without guessing what the maintainer expects.
2. As a new frontend contributor, I want to run the current app locally, so that I can understand the existing user flows before replacing them.
3. As a new frontend contributor, I want to inspect the OpenAPI docs, so that I can learn the backend contract from the app itself.
4. As a new frontend contributor, I want a modern React and TypeScript project structure, so that I can practice current frontend development patterns.
5. As a new frontend contributor, I want to choose and justify frontend tooling, so that I learn how open-source technical tradeoffs are documented.
6. As a new frontend contributor, I want small PRs into a feature branch, so that I can practice review etiquette without destabilizing `main`.
7. As a new frontend contributor, I want CI to validate my PRs, so that I learn how maintainers protect an open-source project.
8. As a maintainer, I want `main` to remain deployable, so that frontend modernization does not break the app during migration.
9. As a maintainer, I want the React frontend to fully replace the old UI, so that the project does not carry two long-term frontend implementations.
10. As a maintainer, I want the final container to remain a single FastAPI runtime with static assets, so that deployment stays simple for operators.
11. As an operator, I want Docker deployment to behave the same after modernization, so that I do not need to run a separate frontend service.
12. As an operator, I want the app to keep serving the UI and API from one origin, so that reverse proxy and PWA setup remain simple.
13. As a user, I want to open Jellyswipe on my phone, so that it feels like a lightweight app rather than a desktop web page.
14. As a user, I want to install Jellyswipe as a PWA, so that I can launch it from my home screen.
15. As a user, I want delegate login to keep working, so that I can enter the app without managing Jellyfin credentials in the browser.
16. As a user, I want to create a hosted room, so that another person can join my swiping session.
17. As a user, I want to share a pairing code, so that my partner can join my hosted room.
18. As a user, I want to join a hosted room by code, so that I can participate in another person's session.
19. As a solo user, I want to create a solo room, so that I can shortlist media by myself.
20. As a host, I want to choose whether the room includes movies, TV shows, or both, so that the deck matches what I want to watch.
21. As a user, I want media cards to show enough title metadata, so that I can decide whether I am interested.
22. As a user, I want artwork to load through the app, so that Jellyfin server details and credentials are not exposed to the browser.
23. As a user, I want to swipe right on media I like, so that Jellyswipe can identify matches.
24. As a user, I want to swipe left on media I do not like, so that I can move through the deck quickly.
25. As a user who cannot or does not want to swipe, I want visible buttons for left and right decisions, so that touch gestures are not the only way to use the app.
26. As a keyboard user, I want controls and dialogs to be reachable and understandable, so that the app is not limited to touch-only interaction.
27. As a hosted-room participant, I want matches to appear when both participants swipe right, so that we know what to watch together.
28. As a solo-mode user, I want right-swiped items to appear as matches, so that solo mode behaves like a personal shortlist.
29. As a user, I want realtime room updates to continue working, so that hosted sessions stay synchronized.
30. As a user, I want basic recovery after refresh, so that I do not lose the active room immediately if I reload.
31. As a user, I want to see current matches, so that I can review the shortlist during a session.
32. As a user, I want to end a session, so that matches are saved and the room lifecycle is clear.
33. As a user, I want optional details like trailers and cast to return later in the roadmap, so that the redesigned app eventually reaches feature parity.
34. As a user, I want watchlist/favorite actions to return later in the roadmap, so that matched media can still be saved in Jellyfin.
35. As a contributor, I want hand-written frontend domain types at first, so that I understand the API shapes before adopting code generation.
36. As a contributor, I want frontend tests from the first setup, so that I learn to protect behavior while refactoring UI.
37. As a contributor, I want manual mobile smoke checks, so that touch, PWA, and layout behavior are validated outside unit tests.
38. As a maintainer, I want screenshots or recordings on UI PRs, so that review can account for visual and interaction changes.
39. As a maintainer, I want backend changes to be coordinated, so that frontend modernization does not accidentally redesign the API or room model.
40. As a maintainer, I want project screenshots updated when React replaces the old UI, so that documentation reflects the shipped app.

## Implementation Decisions

- The modernization will be incremental, but the destination is a complete replacement of the old frontend. Temporary side-by-side development is acceptable as an implementation tactic; two permanent frontends are not.
- The first integration target is a long-lived frontend modernization branch. Small topic branches and PRs should merge into that branch. The integration branch merges to `main` only at usable checkpoints.
- The first merge-to-`main` checkpoint must include delegate login, hosted rooms, solo rooms, deck display, left/right decisions, match display, mobile usability, PWA installability, FastAPI static serving, and one-container Docker deployment.
- React and TypeScript are required for the modernized frontend.
- The exact frontend build tool is intentionally a contributor design decision. Vite is the recommended default candidate because it is simple, common, and fast, but the contributor should document the selected tool and tradeoffs.
- The frontend app should live in a dedicated frontend workspace rather than mixing package manager files into backend concerns.
- Node tooling is allowed at build time only. The production container must not require a Node runtime process.
- The production build should use normal hashed asset filenames. The backend/static integration should serve the generated production HTML and assets instead of disabling cache-friendly output.
- The current API contract is the starting point. Frontend code should call existing endpoints as-is and use the OpenAPI docs as reference.
- API requests should remain same-origin and preserve cookie-based session behavior.
- Realtime room updates should continue to use server-sent events.
- Backend service behavior, database schema, auth/session internals, room matching, and public API shapes should not change unless the frontend is blocked and the maintainer coordinates the backend fix.
- The browser app should start as a single-screen React application. Client-side routing is out of the initial design unless a later UX decision creates real URL needs.
- Initial state management should use React state and custom hooks. A small state library is allowed later if the implementation clearly benefits.
- Initial API types should be hand-written for core concepts such as media cards, room status, matches, current user, room creation, swipe directions, and session events. OpenAPI type generation can be evaluated later.
- Styling is the contributor's choice. Plain CSS, CSS modules, Sass, or Tailwind are acceptable if the tradeoff is documented. CSS-in-JS is not recommended as the first option unless there is a clear reason.
- Swipe behavior should evaluate a focused gesture library. Manual gesture code is acceptable for learning prototypes, but the production implementation should prioritize predictable cross-device behavior.
- PWA behavior is non-negotiable from the start. The implementation must preserve mobile viewport behavior, manifest metadata, icons, service worker serving, and installability.
- The current simple service worker can be preserved initially. PWA generation plugins can be evaluated after the React app is stable.
- Accessibility basics are part of the initial standard: semantic actions, visible focus, readable contrast, reachable dialogs, usable touch targets, meaningful alt text, and non-gesture alternatives for critical actions.
- The contributor will develop against live Jellyfin and TMDB data provided by the maintainer. Secrets must remain local and uncommitted.
- The developer setup documentation should remain current so new contributors can install dependencies, run the app, open API docs, understand CI, and validate production static serving.
- Secondary feature parity can follow after the first usable checkpoint: match history management, trailer playback, cast display, add-to-watchlist/favorites, genre filtering, hide-watched filtering, and advanced visual polish.
- No schema changes are planned for this PRD.
- No new backend API endpoints are planned for the first usable checkpoint.

## Testing Decisions

- Good tests should validate externally observable behavior rather than implementation details. A test should care that a user can create a room, swipe, and see a match; it should not care which component or hook owns an internal variable.
- Frontend testing should start with modest coverage rather than waiting until the redesign is complete.
- The API client should be tested for representative success and failure paths, including delegate login, room creation, boolean setup payloads, deck fetches, swipe submission, and match responses.
- State and interaction tests should cover deck advancement, left/right decisions, match display, loading states, and error states.
- Component tests should cover critical UI surfaces at a smoke level: app shell, authenticated/unauthenticated state, room setup, deck card rendering, match display, and accessible decision buttons.
- Realtime behavior should be tested around the session event interface where practical, especially event handling that updates room/deck/match state.
- PWA behavior requires manual validation in addition to automated tests. Installability, service worker path, mobile viewport, and icon/manifest resolution should be checked before merge-to-`main` checkpoints.
- Mobile swipe behavior requires manual validation on a phone-sized viewport, and ideally on a real touch device, because pointer/touch edge cases are difficult to prove with unit tests alone.
- Docker/static-serving behavior requires production-path validation: build the frontend, serve it through FastAPI, and confirm the Docker image serves UI and API from the same container.
- CI remains responsible for full project validation on PRs. Local contributor expectation is to run the relevant frontend tests while iterating; merge checkpoints should run frontend tests, backend tests, production frontend build, and static-serving/Docker smoke checks.
- Backend tests are required for any coordinated backend/API fixes discovered during frontend implementation.
- Existing backend route tests are prior art for validating API behavior from the outside.
- Existing health and Docker-oriented checks are prior art for validating production readiness.
- Future frontend tests should become prior art for subsequent UI milestones, especially API-client and component behavior tests.

## Out of Scope

- Replacing the FastAPI backend.
- Running the frontend as a separate production service.
- Requiring Node in the final runtime container.
- Redesigning authentication or reintroducing browser username/password login.
- Redesigning the room, swipe, match, or solo-mode domain model.
- Changing database schema as part of the initial frontend modernization.
- Changing public API response shapes unless an endpoint is proven broken and the maintainer coordinates the fix.
- Implementing OpenAPI type generation in the first slice.
- Adding client-side routing in the first slice.
- Completing every secondary feature before the first usable checkpoint.
- Full accessibility audit certification.
- Full offline PWA caching semantics beyond preserving installability and current service worker behavior.
- Supporting multiple long-term frontend implementations.

## Further Notes

- The frontend modernization guide contains the contributor-facing milestone plan and onboarding sequence derived from this PRD.
- The developer guide should be kept current as the frontend build tooling is selected, especially Node runtime requirements, frontend install commands, and production build/static-serving validation.
- The recommended PR workflow is an integration branch such as `frontend/react-modernization` with small topic PRs for scaffolding, API client work, login/session state, room setup, deck/swipe behavior, and matches.
- UI PRs should include screenshots or short recordings. The final replacement checkpoint should update project screenshots.
- Conventional Commits and semantic PR titles remain required project etiquette.
- The existing delegate identity ADR remains authoritative: frontend modernization must preserve server-delegate login and must not add browser-side Jellyfin credential handling.
- The operational hardening ADR remains authoritative: frontend modernization must preserve the one-container deployment model and avoid changing runtime Docker semantics without a separate decision.
