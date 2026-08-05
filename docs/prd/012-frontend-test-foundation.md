# PRD: Frontend Test Foundation (TypeScript)

## Problem Statement

The React + Vite frontend has been **rewritten in TypeScript** on the
[`syarnell/frontend-redesign`](https://github.com/syarnell/jelly-swipe-fork/tree/frontend-redesign)
fork (baseline commit `697dc54`). That rewrite did **not** carry over the test harness an
earlier draft of this PRD stood up against the old `.jsx` code — so the TypeScript
frontend currently has **no test harness at all**. The fork's `frontend/package.json`
declares no test script and no testing dependencies, and the fork's CI
(`.github/workflows/test.yml`) runs only the Python suite. This PRD re-does the
"frontend test foundation" work **against the TypeScript redesign as it exists today**:
standing up the harness and writing a first, meaningful layer of tests.

**Integration model:** this work is authored on a branch off `syarnell/frontend-redesign`
and **PR'd back to that fork**. The baseline is the fork; there are no obsolete `.jsx`
tests to remove (they never existed on the fork), and the CI job is added to the fork's
existing `test.yml` (the `actions/checkout@v6` / `setup-python@v6` / `uv` workflow).

Two constraints shape everything below, because this work doubles as a **learning
exercise for the contributor doing the frontend rewrite**, who is new to front-end
development:

1. **Do not redo the redesign.** Tests describe the current TypeScript code. We do not
   refactor components to make them prettier, more idiomatic, or easier to test, and we
   do not convert any remaining JavaScript (`api.js`) to TypeScript.
2. **Prefer documented hard-to-test code over rewritten code.** Where something is
   awkward to test, we write the best test we can _and leave a comment/TODO explaining
   what makes it hard and how a future refactor could improve it_ — rather than
   changing the source. Those notes are a deliverable, because they teach.

The only source edits permitted are the minimum required to make testing possible at
all: a test script + dev dependencies, a Vitest config block, a small `tsconfig.json`
`types` entry, and **one targeted export in `RoomContextProvider.tsx`** (see
[Context test strategy](#context-test-strategy)). Anything beyond that is out of scope.

## Solution

Adopt **Vitest + React Testing Library** (jsdom environment,
`@testing-library/user-event`) as the frontend test stack. Vitest is chosen because it
reuses the existing Vite config, so `import.meta.env` and asset imports work with minimal
setup — the lowest-friction option for a Vite app and the gentlest on-ramp for a new
developer. This also matches the "Suggested React Stack" in the modernization guide,
which already names Vitest and Testing Library.

Tests are written in **TypeScript** (`*.test.tsx`), matching the redesign, with one
deliberate exception: `api.js` stays JavaScript (the fork left it JS) and its test stays
`api.test.js`. Write tests in a **logic-first** order — cheapest to understand and
highest signal first, then component render/interaction tests — establishing reusable
patterns the contributor can copy. Wire the suite into CI as a separate Node job that
**type-checks and runs the tests**, so the frontend gates pull requests alongside pytest.
Treat every test file as teaching material: liberally commented to explain _what_ is
tested and _why_ the approach was chosen.

Bugs discovered while writing tests are **documented and pinned by skipped "desired
behavior" tests** — not fixed here — consistent with the no-rewrite constraint.

## User Stories

1. As the frontend contributor, I want a working `npm test` in `frontend/`, so that I can run tests while I iterate.
2. As the frontend contributor, I want heavily-commented test files, so that I learn testing patterns from the tests themselves.
3. As the frontend contributor, I want reusable, typed helpers (context wrapper, fetch mock, card factory), so that I can copy them when writing new tests.
4. As the frontend contributor, I want the API client (`api.js`) covered for dev vs prod behavior, so that I trust the request layer.
5. As the frontend contributor, I want the modals and screens covered for their core interactions, so that I can refactor UI without silently breaking flows.
6. As the frontend contributor, I want hard-to-test code (pointer drag) clearly marked with notes instead of rewritten, so that I learn _why_ it is hard and what to do later.
7. As the maintainer, I want frontend tests **and a type-check** to run in CI on every PR, so that the frontend is protected the same way the backend is.
8. As the maintainer, I want bugs found during testing recorded rather than quietly fixed, so that the contributor stays the author of their own fixes.
9. As a future contributor, I want a documented frontend testing convention, so that subsequent UI milestones have prior art to follow.

## Implementation Decisions

- **Stack: Vitest + React Testing Library** with jsdom, `@testing-library/user-event`,
  and `@testing-library/jest-dom`. No Jest.
- **Tooling changes to `frontend/package.json`** (the minimum needed to test):
  - `devDependencies`: `vitest`, `@testing-library/react`, `@testing-library/dom`,
    `@testing-library/user-event`, `@testing-library/jest-dom`, `jsdom`. Install these
    **before** the `tsconfig.json` `types` entry references them (otherwise `tsc` errors
    on missing type definitions).
  - `scripts`: `"test": "vitest run"`, `"test:watch": "vitest"`, and
    `"typecheck": "tsc --noEmit"`.
  - **Version compatibility:** the project pins Vite `^5.4.1`. Use a Vitest release that
    targets Vite 5 (Vitest 2.x or 3.x both support Vite 5) — do not jump to a Vitest major
    that drops Vite 5. `@testing-library/react` 16.x covers React 18. Pin whatever exact
    versions `npm install` resolves into `package-lock.json` so CI's `npm ci` is
    reproducible.
- **Vitest config** lives in a single `test` block inside the existing `vite.config.js`
  (still JS on the fork; not a separate `vitest.config.js`) — one config file is easier
  for a beginner to reason about and it reuses the React plugin automatically. Add the
  `/// <reference types="vitest/config" />` triple-slash so types resolve. Settings:
  `environment: "jsdom"`, `globals: true` (so tests read naturally for a beginner), and a
  `setupFiles` entry pointing at `test/setup.ts` which imports `@testing-library/jest-dom`.
- **TypeScript globals + matcher types.** Because the fork's `tsconfig.json` is `strict`
  with `include: ["./**/*"]`, the `*.test.tsx` files are in the type-checking graph and
  CI type-checks them (see CI below). Add
  `"types": ["vitest/globals", "@testing-library/jest-dom"]` to `tsconfig.json` so the
  Vitest globals (`describe`/`it`/`expect`/`vi`) and the jest-dom matchers
  (`toBeInTheDocument`, …) resolve without per-file imports.
  - **Safety note:** setting `types` restricts which _global_ ambient packages TS
    auto-includes. This is safe here — asset module declarations come from `assets.d.ts`
    via `include`, and `@types/react`/`@types/react-dom` are _imported_ module types
    (unaffected by `types`). The harness slice **must confirm `tsc --noEmit` still passes
    for the app**, not just the tests. Documented fallback if the `types` edit ever
    regresses app type-checking: drop the `types` entry and use triple-slash
    `/// <reference types="vitest/globals" />` (and a jest-dom reference) in `test/setup.ts`
    instead.
- **No asset stub needed.** Vitest runs imports through Vite's own transform pipeline, so
  `import poster from "./assets/moana-poster.jpg"` resolves to a URL string just like in
  the app, and `.css` imports are handled too. (This is precisely why Vitest is lower
  friction than Jest here — Jest would need a `moduleNameMapper` stub.) The fork's
  `assets.d.ts` already declares the asset modules for TypeScript.
- **Test file location: co-located** next to the component (`MovieCard.test.tsx`), so a
  new dev sees the test beside the code it covers.
- **Shared helpers live in a dedicated `frontend/test/` folder** (keeps the flat root
  readable), written in TypeScript except the JS-mirroring `api` test:
  - `test/setup.ts` — imports `@testing-library/jest-dom`; referenced by `setupFiles`.
  - `test/renderWithRoom.tsx` — wraps a component in `RoomContext.Provider` with sensible
    defaults and `vi.fn()` setters, accepting overrides, and returns the typed context so
    tests can assert setter calls. See [Context test strategy](#context-test-strategy).
  - `test/mockFetch.ts` — a helper around `vi.spyOn(global, "fetch")` returning
    configurable `{ ok, json }` responses, for the network-touching components. Because
    `apiFetch` now passes a `URL` object to `fetch`, assertions on the request URL read
    `.href` (or `String(url)`), not a bare string.
  - `test/fixtures.ts` — a `makeCard(overrides: Partial<Card> = {})` factory returning a
    fully-shaped default `Card` and a `makeDeck(n): CardDeck` helper, both typed against
    `./types`. Note the shape on the redesign: `media_id` is a **string**, `duration` is a
    **string**, and `season_count` is `number | undefined` (use `undefined`, never `null`).
    Teaches the typed object-mother/factory pattern and keeps the singular/plural,
    `toFixed`, and `media_type` tests to one line each (e.g. `makeCard({ season_count: 1 })`).
- **`index.tsx` is intentionally not tested** — it is a thin `createRoot` DOM-mount entry
  point with no logic; testing it fights jsdom for no value. Noted as deliberately
  untested.
- **`console` noise**: components log via `console.log`/`console.error` as side effects;
  tests spy/silence these rather than depend on them.
- **No coverage-percentage gate.** The goal is a meaningful, well-explained first layer,
  not a number.
- **Documentation deliverable: a new `frontend/README.md`** (does not exist on the fork)
  is the home for frontend dev docs, with a **Testing** section covering: how to run
  (`npm test`, `npm run test:watch`, `npm run typecheck`); the conventions (co-located
  `*.test.tsx`, the `test/` helpers, the 3-part network assertion contract); the
  **two-RoomContext-instances aside** (see below); the **skipped "desired behavior"
  pattern**, explained as "how to safely document something you want to improve later
  without breaking what works"; and a pointer to the `MovieCard` drag stub as the worked
  example of hard-to-test-but-documented code. A single pointer line is added to
  `DEVELOPER.md`'s existing "Tests, Linting, and Formatting" section linking to
  `frontend/README.md` — keeping that Python-centric doc otherwise untouched.
- **CI**: add a second job named `frontend-test` to the fork's
  `.github/workflows/test.yml`, running **in parallel** with the existing Python `test`
  job (a separate job, not extra steps), on the same `push`/`pull_request` (`**`) triggers
  so it gates PRs the same way. Steps: `actions/checkout@v6` (matching the fork's existing
  job) → `actions/setup-node@v4` (Node **20**, `cache: npm`,
  `cache-dependency-path: frontend/package-lock.json`) → `npm ci` in `frontend/` →
  `npm run typecheck` (`tsc --noEmit`) → `npm test` (`vitest run`). Use `npm ci` (not
  `npm install`) for reproducible installs. The fork already passes `tsc --noEmit` clean
  at baseline, so the type-check gate starts green; keeping it green (app **and** tests)
  is part of acceptance.
- **Pin Node for humans**: add `frontend/.nvmrc` containing `20` (the fork has none), so
  local Node matches CI.
- **Do not add a frontend test hook to `.pre-commit-config.yaml`.** A test run in a git
  hook annoys a learning dev; CI is the right gate. The fork's pre-commit prettier is
  scoped to `types_or: [markdown, yaml, json]`, so it won't touch the new `.tsx`/`.ts`/`.js`
  files.
- **Branch protection / required-check status is out of scope** for this PRD — the
  maintainer configures that directly. This PRD only adds the CI job.

### Context test strategy

The redesign refactored room state: components no longer read a context object directly —
they call a new **`useRoomContext()`** hook from `RoomContextProvider.tsx`, which
**throws** if rendered without a provider. Complicating matters, `App.tsx` declares **its
own** `RoomContext` and exports it, but that is a _different, unused_ instance — the
components consume the module-private `RoomContext` inside `RoomContextProvider.tsx`. A
naive helper that wraps `App.tsx`'s exported context would not reach the components and
they would hit the throw.

Decision:

- **Export the real context.** Add `export` to the `RoomContext` const **and** to the
  `RoomContextType` interface in `RoomContextProvider.tsx` — a one-token, non-behavioral
  source edit, explicitly blessed by this PRD. `test/renderWithRoom.tsx` then wraps
  `<RoomContext.Provider value={ctx}>` with a typed `ctx` (defaults + `vi.fn()` setters,
  overridable) and returns `ctx` so tests can both preset values (e.g. `currentRoomCode`)
  and assert setter calls (e.g. `setCurrentRoomCode`). This keeps the helper close to the
  beginner-friendly pattern and avoids `vi.mock` "magic." If `vi.fn()` setters do not
  satisfy the `Dispatch<SetStateAction<…>>` types under `strict`, a narrow cast in the
  helper is acceptable (the export of `RoomContextType` exists to support precise typing).
- **`App.tsx`'s dead duplicate context is document-only.** It is dead code, not observable
  behavior, so a "desired behavior" test does not fit. Note it in `frontend/README.md`
  (and optionally a one-line code comment): _two `RoomContext` instances exist; only the
  provider's is live; `renderWithRoom` imports the provider's (now-exported) context, not
  App's._ Do not delete App's copy — that would be a redesign edit.

## Testing Decisions

Tests are written in priority order. Each layer is a learning milestone.

1. **`api.js` (pure-ish logic, highest signal) — `api.test.js` (JavaScript):**
   - `getApiBaseUrl()` returns a `URL` whose `.href` is `http://localhost:5005/` (note the
     trailing slash) when `import.meta.env.DEV` is true, and `window.location.origin`
     otherwise (controlled per-test via `vi.stubEnv`).
   - `apiUrl(path)` joins a path against the base via `new URL(path, base)` — e.g.
     `apiUrl('/room').href === 'http://localhost:5005/room'`.
   - `apiFetch` sets `credentials` (`include` in dev, `same-origin` in prod), defaults
     `headers`, and calls `fetch` with the resolved `URL` (asserted via `.href`).
2. **Pure logic inside components** (asserted via rendered output, not by changing source):
   - `SwipePage`: left/right glow opacity thresholds (`±20`) and `/200` clamp to 1;
     `visibleCards` slice-to-5 and reverse ordering.
   - `MovieCard`: `mediaText` (`"movie"`→"Movie", `"tv_show"`→"TV", else empty — the
     `"tv_show"` value is backend-confirmed correct), `seasonsText` singular vs plural vs
     none (via the `season_count !== undefined` guard), and `rating.toFixed(2)` formatting.
3. **Presentational:** `Header` renders the logo image with alt text **when there is no
   room code**, and renders no logo once a room code is set (the conditional is the
   behavior — test both branches).
4. **Render + interaction:**
   - `Intro`: clicking Host/Join opens the right modal; closing resets the relevant state
     (host close resets `movies`/`tvShows`/`isSoloMode`; join close resets `userInputCode`).
   - `HostModal`: the Movies/TV/**Solo** toggles update state; `createSession` POSTs to
     `/room` and stores the returned `pairing_code` as the current room code. The request
     body is `{movies, tv_shows, solo}`.
   - `JoinModal`: input sanitizes to digits (writing through `setUserInputCode`, which now
     lives in context); `joinRoom` POSTs to `/room/{userInputCode}/join` and sets the room
     code on success.
   - `Main`: renders `Intro` with no room code and `SwipePage` (passed the `cardDeck` prop)
     once a code is set; fetches the deck from `/room/{code}/deck` on mount.
   - `SwipePage`: `handleEndSession` POSTs to `/room/{code}/quit` and clears the room code.

- **Behavior over implementation:** tests assert observable behavior (what renders, what
  network call is made), echoing PRD 009's testing philosophy — not internal variable
  ownership.
- **Standard assertion contract for every network action** (`createSession`, `joinRoom`,
  `handleEndSession`, deck fetch) — three parts, no more, no less, for a proportionate
  first pass:
  1. **The request** — `fetch` (via `mockFetch`) was called with the correct URL (asserted
     via `.href`) + method, and for POSTs the expected JSON body (e.g. the
     `{movies, tv_shows, solo}` payload).
  2. **The success effect** — the observable result of `res.ok`, e.g.
     `setCurrentRoomCode` called with the returned `pairing_code`, or the deck rendering.
  3. **One failure path** — either `res.ok === false` _or_ a rejected `fetch` (one, not
     both) leaves state unchanged and does not throw (exercises the `catch`/`console.error`
     path).

### Behaviors that exist vs. don't yet (scope boundary)

The redesign is mid-build: several UI surfaces are rendered but wired to nothing. We test
only what has behavior today. Decomposed tasks must **not** include tests for the
not-yet-implemented items below.

Wired and therefore tested: deck fetch on mount (`Main`), room creation incl. solo
(`HostModal`), room join via context-held code (`JoinModal`), end session (`SwipePage`),
modal open/close + state reset (`Intro`), card flip and derived display (`MovieCard`),
glow math + card-stack slicing (`SwipePage`), the API client (`api.js`).

Not yet implemented — intentionally untested:

- **Swipe → API.** `MovieCard.handlePointerUp` animates the card off-screen but never
  POSTs `/room/{code}/swipe` and never advances the deck (see its
  `// remove card after animation, trigger next card, API call` comment). This is the one
  load-bearing gap we signpost: drop a single
  `it.todo("swiping right should POST to /room/{code}/swipe")` breadcrumb in
  `MovieCard.test.tsx`, so whoever builds it next finds a friendly test-first marker.
- **Match display** — does not exist yet.
- **Dead/static elements** in `SwipePage` — `Undo`, `Shortlist`, `Show Watched`, the
  `Genres` element, and the hardcoded `mode-badge` ("Solo", a literal not wired to
  `isSoloMode`) — have no handlers/wiring; noted as untested-because-unimplemented. No
  `it.todo` for these — that would presume product decisions.
- **`checkSessionStatus`** in `Main.tsx` is written (targets `/room/{code}/status`) but
  commented out; left as-is, untested.

### Hard-to-test code: document, do not rewrite

- **`MovieCard` pointer drag** relies on `setPointerCapture` / `releasePointerCapture`
  and `PointerEvent`, which jsdom does not fully implement. This pass tests the card's
  derived/visual logic and the non-drag flip toggle, and adds a **clearly commented,
  skipped (or minimal) stub** for the drag path explaining the jsdom limitation and what
  a future change (injecting handlers, or an E2E test) would require. This is the
  canonical "hard-to-test, documented" example for the contributor.
- **`import.meta.env.DEV`** must be controllable per test; `vi.stubEnv` is the chosen
  mechanism (used in `api.test.js`), with the fallback documented inline if it proves
  awkward.

### Known issues to capture (document via skipped "desired behavior" tests)

For each known bug we do **not** assert the current (wrong) output — that would lock in
buggy behavior and turn red the moment the contributor fixes it. Instead each bug gets a
test that asserts the **correct / desired** behavior, marked `it.skip` (or `it.todo`)
with a comment block explaining: what the bug is, why the test is skipped, and the cue
"un-skip this and it should pass once you fix X." This way the test file documents the
bug, nothing is red today, and fixing the bug is rewarded with a green test — a gentle
TDD-lite moment that lets the dev improve their code without anything appearing broken.
This is a deliberate morale decision: never break or rewrite the new dev's working code
out from under them.

Bug to capture this way:

- `MovieCard.tsx` — the score is rendered as
  `{rating && <div className="movie-score">IMDb {rating != null ? rating.toFixed(2) : "N/A"}</div>}`.
  Because `&&` short-circuits on falsy values, a card with `rating === 0` evaluates
  `0 && …` to `0`, and React renders a **stray "0"** instead of the score (the inner
  `rating != null` ternary is **dead code** for the zero case — the outer `&&` already
  gated it, so the `IMDb 0.00` div never appears). This is the classic React falsy-zero
  JSX pitfall — an excellent beginner teaching case. Skipped/`todo` test: a card with
  `rating === 0` shows `IMDb 0.00` and no stray "0"; un-skip it once the guard is fixed
  (e.g. `rating != null && …`).

Note: this remains the **only verified bug** in the redesign. The backend
(`jellyfin_media_item.py`) genuinely emits `media_type` values `"movie"`/`"tv_show"` and a
`season_count`, so `MovieCard`'s `"tv_show"`→"TV" mapping is consistent, not a bug. The
`{movies, tv_shows, solo}` host payload and the `userInputCode`-driven join are likewise
consistent. The duplicate `RoomContext` in `App.tsx` is dead code, documented (not tested)
per [Context test strategy](#context-test-strategy).

## Acceptance Criteria

This PRD is complete when all of the following hold:

1. `npm test` in `frontend/` runs Vitest and exits 0, with every non-skipped test passing.
2. `npm run typecheck` (`tsc --noEmit`) passes for **both** the app and the new test files
   (i.e. the `tsconfig` `types` edit did not regress app type-checking).
3. The harness exists and is used: `vite.config.js` has the `test` block, and
   `test/setup.ts`, `test/renderWithRoom.tsx`, `test/mockFetch.ts`, and `test/fixtures.ts`
   are all present and typed.
4. `RoomContextProvider.tsx` exports `RoomContext` and `RoomContextType`, and
   `renderWithRoom` consumes the provider's context (not App's).
5. `api.js` is covered (in `api.test.js`): dev vs prod base URL as `URL` objects, `apiUrl`
   path join, and `apiFetch` credentials/headers/URL.
6. Each wired component has a co-located test file: `Header`, `Intro`, `HostModal`,
   `JoinModal`, `Main`, `SwipePage`, `MovieCard`.
7. Each network action follows the 3-part assertion contract (request + success + one
   failure path), with the `HostModal` request asserting the `{movies, tv_shows, solo}`
   body and the end-session call hitting `/room/{code}/quit`.
8. The rating-zero known bug has a skipped "desired behavior" test with an explanatory
   comment; the `MovieCard` pointer-drag skip stub and the swipe
   `it.todo("…POST to /room/{code}/swipe")` breadcrumb both exist.
9. The `frontend-test` CI job runs `typecheck` + `test` on PRs in the fork's `test.yml`,
   and `frontend/.nvmrc` pins Node 20.
10. `frontend/README.md` exists with the Testing section described above (including the
    two-RoomContext-instances aside), and `DEVELOPER.md`'s "Tests, Linting, and Formatting"
    section links to it.
11. **Gate:** every test file opens with a brief, beginner-oriented comment explaining what
    it covers and any non-obvious technique used. The teaching comments are a primary
    deliverable, not decoration.

No test-count or per-file minimum is set — criterion 6 (a file per wired component) plus
the assertion contract is the bar; counting tests would only invite gaming.

## Out of Scope

- Refactoring, restructuring, or changing the public shape of any `frontend/` component
  to make it more testable (beyond the single blessed `export` in `RoomContextProvider.tsx`).
- Converting `api.js` (or any other deliberately-JS file) to TypeScript — the redesign
  left it JS; the test mirrors that.
- Fixing the bug listed under "Known issues to capture" — it is documented only.
- Backend changes and any tests of the FastAPI app (already covered by pytest).
- End-to-end / browser-automation tests (Playwright, Cypress).
- Exhaustive pointer-drag gesture testing in `MovieCard` (jsdom limitation; see above).
- A coverage-percentage gate or 100%-coverage goal.
- Production build / static-serving / Docker validation (covered by PRD 009's checkpoints).
- Adopting/merging the TypeScript redesign itself — the baseline is assumed to be the fork;
  this PRD only adds tests, type-check wiring, and CI on top of it.

## Further Notes

- This PRD follows the repo PRD shape used by [PRD 009](009-frontend-modernization.md)
  and [PRD 011](011-rehome-domain-types.md): Problem Statement, Solution, User Stories,
  Implementation Decisions, Testing Decisions, Out of Scope, Further Notes.
- It implements the "frontend tests from the first setup" intent of PRD 009 and the
  "Frontend Testing" section of the modernization guide, scoped to the **TypeScript** code
  on `syarnell/frontend-redesign` (`697dc54`).
- **Decomposition (for `/to-issues`)** — a tracer-bullet first slice, then one ticket per
  test layer. Slices 2–8 depend only on slice 1 and can be done in any order / parallel,
  so a learning dev can pick them off one at a time:
  1. **Harness tracer bullet** — `package.json` deps/scripts (incl. `typecheck`),
     `vite.config.js` test block, the `tsconfig.json` `types` entry, the
     `RoomContextProvider.tsx` exports, `test/setup.ts` + the three helpers
     (`renderWithRoom.tsx`, `mockFetch.ts`, `fixtures.ts`), the single smallest real test
     (`Header.test.tsx`), and the `frontend-test` CI job (typecheck + test) +
     `frontend/.nvmrc`. Proves the whole pipeline (local + CI green, types green)
     end-to-end before any volume of tests is written.
  2. `api.test.js` — URL-object base, path join, `apiFetch` credentials/URL.
  3. `MovieCard.test.tsx` — derived display + flip, the drag skip stub, the swipe
     `it.todo`, and the rating-zero known-bug skip test.
  4. `SwipePage.test.tsx` — glow math, card-stack slicing, end-session contract (`/quit`).
  5. `Intro.test.tsx` — modal open/close + state reset.
  6. `HostModal.test.tsx` — Movies/TV/Solo toggles + create-session contract
     (`{movies, tv_shows, solo}`).
  7. `JoinModal.test.tsx` — input sanitization + join contract (context-held code).
  8. `Main.test.tsx` — deck-fetch contract + Intro/SwipePage switching.
  9. `frontend/README.md` + the `DEVELOPER.md` pointer line.
- **No ADR.** The Vitest-vs-Jest choice is cheap to reverse, unsurprising (the
  modernization guide already names Vitest as the default), and not a close trade-off. The
  one mildly surprising decision — exporting `RoomContext` from the provider _for tests_ —
  is cheap to reverse and is explained in `frontend/README.md`, so it too fails the ADR bar.
  No ADR is recorded.
- Conventional Commits apply: e.g. `test(frontend): cover api client`,
  `chore(frontend): add vitest harness`, `ci: run frontend tests and typecheck on PRs`.
