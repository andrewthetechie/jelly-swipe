// Vitest setup file — runs once before each test file (wired via `setupFiles`
// in vite.config.js). Its only job is to register the jest-dom matchers, which
// add readable DOM assertions like `expect(el).toBeInTheDocument()` and
// `expect(el).toHaveClass("flipped")` on top of Vitest's built-in `expect`.
import "@testing-library/jest-dom";

// --- jsdom pointer-capture stubs -------------------------------------------
// jsdom does not implement the Pointer Capture API (setPointerCapture /
// releasePointerCapture / hasPointerCapture). CardItemView's drag handlers call
// these, so firing pointer events in a test would otherwise throw
// "setPointerCapture is not a function". We install harmless no-op stubs here,
// at the harness level, so any test that fires pointer events doesn't crash.
//
// NOTE: these stubs only stop the crash — they do NOT make jsdom a real
// pointer-driven browser. Full drag-gesture behaviour still can't be tested in
// jsdom; see the documented drag stub in CardItemView.test.tsx for the why.
if (!Element.prototype.setPointerCapture) {
  Element.prototype.setPointerCapture = () => {};
}
if (!Element.prototype.releasePointerCapture) {
  Element.prototype.releasePointerCapture = () => {};
}
if (!Element.prototype.hasPointerCapture) {
  Element.prototype.hasPointerCapture = () => false;
}

// --- jsdom <dialog> modal-API shims -------------------------------------------------
// jsdom does not implement the HTMLDialogElement modal API: HTMLDialogElement
// extends plain HTMLElement (no showModal / close, no `cancel` event, no top
// layer). The Modal component calls showModal() on mount and close() on
// dismissal, so without these stubs every Modal test would throw
// "dialog.showModal is not a function". These harness-level shims only toggle
// the `open` attribute — enough for jsdom tests — and are NOT a browser
// polyfill shipped in app code.
interface DialogShim {
  showModal?: () => void;
  close?: () => void;
}
const dialogProto = window.HTMLDialogElement?.prototype as unknown as DialogShim | undefined;
if (dialogProto && typeof dialogProto.showModal !== "function") {
  dialogProto.showModal = function (this: HTMLDialogElement) {
    this.setAttribute("open", "");
  };
}
if (dialogProto && typeof dialogProto.close !== "function") {
  dialogProto.close = function (this: HTMLDialogElement) {
    this.removeAttribute("open");
  };
}
// --- jsdom matchMedia stub ---------------------------------------------------
// jsdom (as configured here) does not implement `window.matchMedia`. The
// leaving-card exit animation (issue #360) reads it to derive its inline
// transition duration, and the leaving-card hook reads it for the unmount hold.
// This harness-level stub defaults to `matches: false` (the non-reduced-motion
// case); reduced-motion tests override it per-test via `vi.stubGlobal`.
if (typeof window.matchMedia !== "function") {
  const createMediaQueryList = () => ({
    matches: false,
    media: "(prefers-reduced-motion: reduce)",
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
    onchange: null,
  })
  Object.defineProperty(window, "matchMedia", {
    value: () => createMediaQueryList(),
    writable: true,
    configurable: true,
  })
}

import { vi } from "vitest"
import { createMockEventSource } from "./mockEventSource"

if (!globalThis.EventSource) {
  const EventSourceMock = vi.fn(function (url: string) {
    const mock = createMockEventSource()
    mock.url = url
    return mock as unknown as EventSource
  }) as unknown as typeof EventSource

  Object.defineProperty(EventSourceMock, "CONNECTING", {
    value: 0,
    writable: false,
  })
  Object.defineProperty(EventSourceMock, "OPEN", {
    value: 1,
    writable: false,
  })
  Object.defineProperty(EventSourceMock, "CLOSED", {
    value: 2,
    writable: false,
  })

  vi.stubGlobal("EventSource", EventSourceMock)
}
