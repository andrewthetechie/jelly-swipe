import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { renderHook, waitFor } from "@testing-library/react"
import useMovieCast from "./useMovieCast"
import { mockFetch } from "./test/mockFetch"
import { makeCastMember, makeCast } from "./test/fixtures"

describe("useMovieCast", () => {
  beforeEach(() => {
    vi.spyOn(console, "error").mockImplementation(() => {})
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe("successful fetch", () => {
    it("fetches cast and sets state correctly", async () => {
      const cast = makeCast(2)
      const spy = mockFetch({ ok: true, body: { cast } })

      const { result } = renderHook(() => useMovieCast("media123"))


      expect(result.current.isLoading).toBe(true)

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.cast).toEqual(cast)
      expect(result.current.error).toBeNull()

      const url = spy.mock.calls[0][0] as URL
      expect(url.href).toContain("/cast/media123")
    })

    it("uses GET method with correct headers", async () => {
      const cast = makeCast(1)
      const spy = mockFetch({ ok: true, body: { cast } })

      renderHook(() => useMovieCast("media456"))

      await waitFor(() => {
        expect(spy).toHaveBeenCalled()
      })

      const options = spy.mock.calls[0][1] as RequestInit
      expect(options.method).toBe("GET")
      expect(options.headers).toEqual({ "Content-Type": "application/json" })
    })
  })

  describe("error handling", () => {
    it("sets error on non-ok response", async () => {
      mockFetch({ ok: false })

      const { result } = renderHook(() => useMovieCast("media789"))

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.error).toBe("Error fetching cast")
      expect(result.current.cast).toEqual([])
    })

    it("sets error on network error (fetch rejection)", async () => {
      mockFetch({ reject: true })
      const consoleErrorSpy = vi.spyOn(console, "error")

      const { result } = renderHook(() => useMovieCast("media000"))

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.error).toBe("Error fetching cast")
      expect(result.current.cast).toEqual([])
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        expect.stringContaining("Error fetching cast"),
        expect.any(Error),
      )
    })
  })

  describe("re-fetch on mediaId change", () => {
    it("refetches cast when mediaId prop changes", async () => {
      const castA = makeCast(1, () => ({ name: "Actor A" }))
      const castB = makeCast(1, () => ({ name: "Actor B" }))
      const spy = mockFetch({ ok: true, body: { cast: castA } })

      const { result, rerender } = renderHook(
        ({ mediaId }) => useMovieCast(mediaId),
        { initialProps: { mediaId: "mediaA" } },
      )

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.cast).toEqual(castA)
      expect(spy.mock.calls).toHaveLength(1)

      spy.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ cast: castB }),
      } as Response)

      rerender({ mediaId: "mediaB" })

      await waitFor(() => {
        expect(spy.mock.calls.length).toBeGreaterThan(1)
      })

      const newUrl = spy.mock.calls[1][0] as URL
      expect(newUrl.href).toContain("/cast/mediaB")
    })
  })

  describe("edge cases", () => {
    it("handles empty cast array", async () => {
      mockFetch({ ok: true, body: { cast: [] } })

      const { result } = renderHook(() => useMovieCast("media555"))

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.cast).toEqual([])
      expect(result.current.error).toBeNull()
    })

    it("clears error on successful refetch after prior error", async () => {
      const spy = mockFetch({ ok: false })

      const { result, rerender } = renderHook(
        ({ mediaId }) => useMovieCast(mediaId),
        { initialProps: { mediaId: "media1" } },
      )

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.error).toBe("Error fetching cast")

      spy.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ cast: makeCast(1) }),
      } as Response)

      rerender({ mediaId: "media2" })

      await waitFor(() => {
        expect(result.current.error).toBeNull()
      })

      expect(result.current.cast).toHaveLength(1)
    })
  })
})
