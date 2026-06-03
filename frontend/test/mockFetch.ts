// mockFetch — a small wrapper around `vi.spyOn(global, "fetch")` for the
// network-touching components (HostModal, JoinModal, SwipePage, Main).
//
// It replaces the real `fetch` with a spy that resolves to a fake Response
// shaped just enough for our code: `{ ok, json() }`. Pass `reject: true` to
// simulate a network error (the promise rejects) so tests can exercise the
// `catch`/`console.error` failure path.
//
// Returns the spy so tests can assert how `fetch` was called. NOTE: our
// `apiFetch` passes a `URL` OBJECT (not a string) to `fetch`, so assert the
// request URL via the first argument's `.href` (or `String(url)`), e.g.
//   const url = spy.mock.calls[0][0] as URL;
//   expect(url.href).toBe("http://localhost:5005/room");
//
// NOTE: we spy on `globalThis.fetch` rather than the Node-only `global`.
// `globalThis` is the standard, environment-agnostic handle, and our tsconfig
// restricts ambient `types`, so the Node-only `global` name isn't in scope.
import { vi, type MockInstance } from "vitest";

export interface MockFetchOptions {
  // Response.ok — drives the success vs. failure branch in the components.
  ok?: boolean;
  // The body returned by `res.json()`.
  body?: unknown;
  // When true, the fetch promise rejects (simulates a dropped network call).
  reject?: boolean;
}

export function mockFetch(options: MockFetchOptions = {}): MockInstance {
  const { ok = true, body = {}, reject = false } = options;

  const spy = vi.spyOn(globalThis, "fetch");

  if (reject) {
    spy.mockRejectedValue(new Error("network error"));
  } else {
    spy.mockResolvedValue({
      ok,
      json: () => Promise.resolve(body),
    } as Response);
  }

  return spy;
}
