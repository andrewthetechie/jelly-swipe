// api.test.js — tests for the request layer (api.js).
//
// This is the ONE test file written in JavaScript, on purpose: api.js was left
// as JS in the redesign, so its test mirrors it (and `tsconfig` has
// checkJs: false, so it isn't type-checked — no types needed here).
//
// Two techniques worth understanding:
//
// 1. `vi.stubEnv('DEV', true|false)` — api.js branches on `import.meta.env.DEV`
//    (Vite's dev-vs-prod flag). We can't change the real build mode mid-test,
//    so we stub that env value per test and restore it in afterEach with
//    `vi.unstubAllEnvs()`.
//
// 2. URL semantics — note api.js returns `URL` OBJECTS, not strings. A bare
//    `new URL('http://localhost:5005')` normalises to a trailing slash, so its
//    `.href` is `'http://localhost:5005/'`. And `new URL('/room', base)`
//    resolves the path against the base. We therefore assert on `.href`
//    throughout, never against a raw string.
import { afterEach, describe, expect, it, vi } from "vitest";
import { getApiBaseUrl, apiUrl, apiFetch } from "./api";

afterEach(() => {
  // Undo any vi.stubEnv / vi.stubGlobal so tests don't leak into each other.
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("getApiBaseUrl", () => {
  it("uses the current window origin when available", () => {
    vi.stubEnv("DEV", true);
    vi.stubGlobal("location", { origin: "http://localhost:4173" });
    expect(getApiBaseUrl().href).toBe("http://localhost:4173/");
  });

  it("falls back to current origin when no browser location exists", () => {
    vi.stubEnv("DEV", false);
    vi.unstubAllGlobals();
    expect(getApiBaseUrl().href).toBe(new URL("/", window.location.origin).href)
  });
});

describe("apiUrl", () => {
  it("joins a path against the current origin", () => {
    vi.stubEnv("DEV", true);
    vi.stubGlobal("location", { origin: "http://localhost:4173" });
    expect(apiUrl("/room").href).toBe("http://localhost:4173/room");
    expect(apiUrl("/room/1234/deck").href).toBe(
      "http://localhost:4173/room/1234/deck",
    );
  });
});

describe("apiFetch", () => {
  it("sends same-origin credentials and the resolved URL", async () => {
    vi.stubEnv("DEV", true);
    vi.stubGlobal("location", { origin: "http://localhost:4173" });
    const spy = vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: true });

    await apiFetch("/room", { method: "POST" });

    expect(spy).toHaveBeenCalledTimes(1);
    const [url, options] = spy.mock.calls[0];
    // First arg is a URL object — assert via .href, not as a string.
    expect(url.href).toBe("http://localhost:4173/room");
    expect(options.method).toBe("POST");
    expect(options.credentials).toBe("same-origin");
  });

  it("uses the current origin in production-like contexts", async () => {
    vi.stubEnv("DEV", false);
    vi.stubGlobal("location", { origin: "https://example.test" });
    const spy = vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: true });

    await apiFetch("/room");

    const [url, options] = spy.mock.calls[0];
    expect(url.href).toBe("https://example.test/room");
    expect(options.credentials).toBe("same-origin");
  });

  it("defaults headers to {} when none are supplied", async () => {
    vi.stubEnv("DEV", true);
    const spy = vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: true });

    await apiFetch("/room");

    const [, options] = spy.mock.calls[0];
    expect(options.headers).toEqual({});
  });

  it("preserves headers the caller supplies", async () => {
    vi.stubEnv("DEV", true);
    const spy = vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: true });
    const headers = { "Content-Type": "application/json" };

    await apiFetch("/room", { method: "POST", headers });

    const [, options] = spy.mock.calls[0];
    expect(options.headers).toEqual(headers);
  });
});
