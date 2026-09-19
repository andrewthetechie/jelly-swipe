// stubMatchMedia — stub `window.matchMedia` to a fixed `matches` value for the
// reduced-motion tests (issue #360). The harness-level stub in `setup.ts`
// defaults to `matches: false`; tests flip it per-test via this helper and
// restore with `vi.unstubAllGlobals()` in their `afterEach`.
import { vi } from "vitest";

export function stubMatchMedia(matches: boolean) {
  const mql = {
    matches,
    media: "(prefers-reduced-motion: reduce)",
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
    onchange: null,
  };
  vi.stubGlobal("matchMedia", vi.fn(() => mql));
}
