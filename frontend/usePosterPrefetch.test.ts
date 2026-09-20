// usePosterPrefetch.test.ts — covers the SwipePage poster preload hook (issue
// #350): warms each URL exactly once, skips null/empty entries, and dedupes
// across re-renders with overlapping decks.
//
// jsdom's `Image` assigns `src` without fetching, so we stub it per-test to
// record the assigned srcs, then restore with `vi.unstubAllGlobals()` in
// `afterEach` (same pattern as `test/stubMatchMedia.ts`).
import { renderHook } from "@testing-library/react"
import { usePosterPrefetch } from "./usePosterPrefetch"

// Records every `src` assigned to a warmed `Image` in call order, and keeps
// the created instances so tests can assert their `decoding` setting.
const assignedSrcs: string[] = []
const createdImages: ImageMock[] = []

class ImageMock {
  decoding: string = "sync"
  private _src: string = ""

  constructor() {
    createdImages.push(this)
  }

  set src(value: string) {
    this._src = value
    assignedSrcs.push(value)
  }

  get src() {
    return this._src
  }
}

describe("usePosterPrefetch", () => {
  beforeEach(() => {
    assignedSrcs.length = 0
    createdImages.length = 0
    vi.stubGlobal("Image", ImageMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it("warms each URL exactly once with decoding set to async", () => {
    renderHook(() => usePosterPrefetch(["/a.jpg", "/b.jpg", "/c.jpg"]))

    expect(assignedSrcs).toEqual(["/a.jpg", "/b.jpg", "/c.jpg"])
    expect(createdImages).toHaveLength(3)
    for (const img of createdImages) {
      expect(img.decoding).toBe("async")
    }
  })

  it("skips null and empty entries", () => {
    renderHook(() => usePosterPrefetch(["/a.jpg", null, "", undefined]))

    expect(assignedSrcs).toEqual(["/a.jpg"])
  })

  it("dedupes across re-renders with overlapping decks", () => {
    const { rerender } = renderHook(({ urls }) => usePosterPrefetch(urls), {
      initialProps: { urls: ["/a.jpg", "/b.jpg"] },
    })

    rerender({ urls: ["/b.jpg", "/c.jpg"] })

    expect(assignedSrcs).toEqual(["/a.jpg", "/b.jpg", "/c.jpg"])
  })

  it("does not re-warm a URL on an identical re-render", () => {
    const { rerender } = renderHook(({ urls }) => usePosterPrefetch(urls), {
      initialProps: { urls: ["/a.jpg"] },
    })

    rerender({ urls: ["/a.jpg"] })

    expect(assignedSrcs).toEqual(["/a.jpg"])
  })
})
