// Vitest setup file — runs once before each test file (wired via `setupFiles`
// in vite.config.js). Its only job is to register the jest-dom matchers, which
// add readable DOM assertions like `expect(el).toBeInTheDocument()` and
// `expect(el).toHaveClass("flipped")` on top of Vitest's built-in `expect`.
import "@testing-library/jest-dom";

// --- jsdom pointer-capture stubs -------------------------------------------
// jsdom does not implement the Pointer Capture API (setPointerCapture /
// releasePointerCapture / hasPointerCapture). MovieCard's drag handlers call
// these, so firing pointer events in a test would otherwise throw
// "setPointerCapture is not a function". We install harmless no-op stubs here,
// at the harness level, so any test that fires pointer events doesn't crash.
//
// NOTE: these stubs only stop the crash — they do NOT make jsdom a real
// pointer-driven browser. Full drag-gesture behaviour still can't be tested in
// jsdom; see the documented drag stub in MovieCard.test.tsx for the why.
if (!Element.prototype.setPointerCapture) {
  Element.prototype.setPointerCapture = () => {};
}
if (!Element.prototype.releasePointerCapture) {
  Element.prototype.releasePointerCapture = () => {};
}
if (!Element.prototype.hasPointerCapture) {
  Element.prototype.hasPointerCapture = () => false;
}
