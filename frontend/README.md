# Jelly-Swipe Frontend

A React + Vite single-page app (written in TypeScript) for the Jelly-Swipe
"swipe to pick something to watch" flow.

## Development

```bash
npm install      # install dependencies
npm run dev      # start the Vite dev server
npm run build    # production build into dist/
```

Node 20 is pinned via `.nvmrc` (run `nvm use`) so local and CI match.

## Testing

The frontend is tested with [Vitest](https://vitest.dev) + [React Testing
Library](https://testing-library.com/docs/react-testing-library/intro/), running
in a `jsdom` environment. Vitest reuses the Vite config, so asset imports and
`import.meta.env` work in tests with almost no extra setup.

### How to run

```bash
npm test          # run the suite once (vitest run) — what CI runs
npm run test:watch  # re-run on change while you iterate
npm run typecheck   # tsc --noEmit; CI runs this too, so keep it green
```

CI (`.github/workflows/test.yml`, the `frontend-test` job) runs `npm ci`, then
`npm run typecheck`, then `npm test` on every push and PR — the frontend gates
PRs the same way the Python suite does.

### Conventions

- **Co-located tests.** A component's test sits next to it: `MovieCard.tsx` →
  `MovieCard.test.tsx`. A new contributor sees the test beside the code it covers.
- **One JavaScript exception.** `api.js` was deliberately left as JavaScript, so
  its test is `api.test.js` (also JS). Everything else is `*.test.tsx`.
- **Shared helpers live in `test/`.** Copy these when writing a new test:
  - `test/setup.ts` — registers the jest-dom matchers (e.g.
    `toBeInTheDocument`) and installs no-op `setPointerCapture` stubs jsdom
    lacks. Wired in via `setupFiles`; you never import it directly.
  - `test/renderWithRoom.tsx` — renders a component inside the room context with
    sensible defaults and `vi.fn()` setters. Use it for **any** component that
    calls `useRoomContext()` (which is most of them). Pass overrides to preset
    values (`{ currentRoomCode: "1234" }`) and read the returned `ctx` to assert
    a setter was called (`expect(ctx.setCurrentRoomCode).toHaveBeenCalledWith(…)`).
  - `test/mockFetch.ts` — swaps `globalThis.fetch` for a spy resolving to a fake
    `{ ok, json }` response (or rejecting, with `{ reject: true }`). Use it for
    any component that makes a network call. It returns the spy so you can assert
    on the request.
  - `test/fixtures.ts` — `makeCard(overrides)` / `makeDeck(n)` factories that
    return fully-shaped `Card` data. Override only the field a test cares about.
- **The 3-part network assertion contract.** Every network action
  (`createSession`, `joinRoom`, `handleEndSession`, the deck fetch) is asserted
  in exactly three parts — no more, no less:
  1. **The request** — `fetch` was called with the right URL and method (and,
     for POSTs, the expected JSON body). Because `apiFetch` passes a **`URL`
     object** to `fetch`, assert the URL via its `.href`, not as a bare string.
  2. **The success effect** — the observable result of `res.ok` (e.g.
     `setCurrentRoomCode` called with the returned `pairing_code`, or the deck
     rendering).
  3. **One failure path** — `ok: false` _or_ a rejected fetch leaves state
     unchanged and does not throw. Silence the expected `console.error` with a
     spy so the output stays clean.

### The two `RoomContext` instances (why the provider's context is exported)

There are **two** separate `RoomContext` objects in this codebase:

- `App.tsx` declares and exports one — but it is **dead/unused**.
- `RoomContextProvider.tsx` creates the **live** one — the object the components
  actually read through `useRoomContext()`.

`renderWithRoom` imports the **provider's** context (which is `export`ed for
exactly this reason). Wrapping App's copy instead would not reach the components,
and they would hit the `useRoomContext must be used within a RoomContextProvider`
throw. So: never wire a test to App's `RoomContext` — always go through
`renderWithRoom`.

### The skipped "desired behavior" pattern

When you find a bug, it's tempting to assert the current (wrong) output. Don't —
that locks the bug in and turns the test red the moment someone fixes it.
Instead, write the test for the **desired** behavior and mark it `it.skip` (or
`it.todo`) with a comment explaining the bug and a cue like _"un-skip this once
you fix X."_ Nothing is red today, the bug is documented in the test file, and
fixing it is rewarded with a green test — a gentle, low-pressure way to improve
code later without breaking anything that works now.

Worked example: the **rating-zero** test in `MovieCard.test.tsx`. The score is
rendered with `{rating && …}`, and `&&` short-circuits on falsy values — so a
card with `rating === 0` renders a stray `0` instead of `IMDb 0.00` (the classic
React falsy-zero JSX pitfall). The skipped test asserts the correct output and
explains exactly what to change.

### Hard-to-test code: document, don't rewrite

Some code is genuinely hard to test in jsdom, and the policy here is to write the
best test we can and **document the gap** rather than rewrite working source to
make it convenient.

Worked example: the **pointer-drag stub** in `MovieCard.test.tsx`. The drag
gesture uses the Pointer Capture API (`setPointerCapture` /
`releasePointerCapture`) and real `PointerEvent`s, which jsdom doesn't fully
implement. `test/setup.ts` stubs the capture methods so firing pointer events
doesn't crash (this is enough for `SwipePage`'s glow-opacity math, which only
needs `dragX` to update), but a full drag-gesture assertion still can't be done
in jsdom — so that test is a clearly-commented `it.skip` that explains the
limitation and what a future change (extracting the pointer math into a pure
function, or an end-to-end test in a real browser) would require.

There is also an `it.todo("swiping right should POST to /room/{code}/swipe")`
breadcrumb in `MovieCard.test.tsx`: the swipe gesture animates the card away but
doesn't yet POST to the swipe endpoint or advance the deck. The todo marks that
spot test-first for whoever builds it next.
