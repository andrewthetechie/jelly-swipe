import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { renderHook, waitFor } from "@testing-library/react"
import useMovieCast from "./useMovieCast"
import { makeCast } from "./test/fixtures"
import * as roomApi from "./roomApi"

vi.mock("./roomApi", () => ({
  fetchCast: vi.fn(),
}))

const fetchCastMock = vi.mocked(roomApi.fetchCast)

describe("useMovieCast", () => {
  beforeEach(() => {
    vi.spyOn(console, "error").mockImplementation(() => {})
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe("successful fetch", () => {
    it("fetches cast and sets state correctly", async () => {
      const cast = makeCast(2)
      fetchCastMock.mockResolvedValueOnce({ cast })

      const { result } = renderHook(() => useMovieCast("media123"))

      expect(result.current.isLoading).toBe(true)

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.cast).toEqual(cast)
      expect(result.current.error).toBeNull()
      expect(fetchCastMock).toHaveBeenCalledWith("media123", expect.any(AbortSignal))
    })
  })

  describe("error handling", () => {
    it("sets error on fetch rejection", async () => {
      fetchCastMock.mockRejectedValueOnce(new Error("Error fetching cast"))

      const { result } = renderHook(() => useMovieCast("media789"))

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.error).toBe("Error fetching cast")
      expect(result.current.cast).toEqual([])
    })

    it("sets error on network error", async () => {
      fetchCastMock.mockRejectedValueOnce(new Error("network error"))
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
      fetchCastMock.mockResolvedValueOnce({ cast: castA })
      fetchCastMock.mockResolvedValueOnce({ cast: castB })

      const { result, rerender } = renderHook(
        ({ mediaId }) => useMovieCast(mediaId),
        { initialProps: { mediaId: "mediaA" } },
      )

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.cast).toEqual(castA)
      expect(fetchCastMock.mock.calls).toHaveLength(1)

      rerender({ mediaId: "mediaB" })

      await waitFor(() => {
        expect(fetchCastMock.mock.calls.length).toBeGreaterThan(1)
      })

      expect(fetchCastMock).toHaveBeenNthCalledWith(2, "mediaB", expect.any(AbortSignal))
    })
  })

  describe("edge cases", () => {
    it("handles empty cast array", async () => {
      fetchCastMock.mockResolvedValueOnce({ cast: [] })

      const { result } = renderHook(() => useMovieCast("media555"))

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.cast).toEqual([])
      expect(result.current.error).toBeNull()
    })

    it("clears error on successful refetch after prior error", async () => {
      fetchCastMock.mockRejectedValueOnce(new Error("Error fetching cast"))
      fetchCastMock.mockResolvedValueOnce({ cast: makeCast(1) })

      const { result, rerender } = renderHook(
        ({ mediaId }) => useMovieCast(mediaId),
        { initialProps: { mediaId: "media1" } },
      )

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.error).toBe("Error fetching cast")

      rerender({ mediaId: "media2" })

      await waitFor(() => {
        expect(result.current.error).toBeNull()
      })

      expect(result.current.cast).toHaveLength(1)
    })
  })
})
