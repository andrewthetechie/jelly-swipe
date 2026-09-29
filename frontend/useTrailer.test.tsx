import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { renderHook, waitFor, act } from "@testing-library/react"
import useTrailer from "./useTrailer"
import * as roomApi from "./roomApi"
import { RoomApiError } from "./roomApi"

vi.mock("./roomApi", async () => {
  const actual = await vi.importActual<typeof import("./roomApi")>("./roomApi")
  return {
    ...actual,
    fetchTrailer: vi.fn(),
  }
})

const fetchTrailerMock = vi.mocked(roomApi.fetchTrailer)

describe("useTrailer", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe("in-flight", () => {
    it("sets trailerState to 'loading' while the request is in flight", async () => {
      let resolveTrailer!: (value: { youtube_key: string }) => void
      fetchTrailerMock.mockReturnValueOnce(
        new Promise((resolve) => {
          resolveTrailer = resolve
        }),
      )

      const { result } = renderHook(() => useTrailer("media123"))

      act(() => {
        result.current.loadTrailer()
      })

      expect(result.current.trailerState).toBe("loading")
      expect(fetchTrailerMock).toHaveBeenCalledWith("media123", expect.any(AbortSignal))

      // Resolve so the pending promise doesn't linger after the test.
      await act(async () => {
        resolveTrailer({ youtube_key: "abc123" })
      })
    })
  })

  describe("success", () => {
    it("sets trailerKey and trailerState to 'playing'", async () => {
      fetchTrailerMock.mockResolvedValueOnce({ youtube_key: "abc123" })

      const { result } = renderHook(() => useTrailer("media123"))

      act(() => {
        result.current.loadTrailer()
      })

      await waitFor(() => {
        expect(result.current.trailerState).toBe("playing")
      })

      expect(result.current.trailerKey).toBe("abc123")
    })
  })

  describe("404 RoomApiError", () => {
    it("sets trailerState to 'unavailable' without console.error", async () => {
      const errSpy = vi.spyOn(console, "error").mockImplementation(() => {})
      fetchTrailerMock.mockRejectedValueOnce(new RoomApiError(404, "Not Found", "fetching trailer"))

      const { result } = renderHook(() => useTrailer("media123"))

      act(() => {
        result.current.loadTrailer()
      })

      await waitFor(() => {
        expect(result.current.trailerState).toBe("unavailable")
      })

      expect(result.current.trailerKey).toBeNull()
      expect(errSpy).not.toHaveBeenCalled()
      errSpy.mockRestore()
    })
  })

  describe("network rejection", () => {
    it("sets trailerState to 'unavailable' and logs console.error", async () => {
      const errSpy = vi.spyOn(console, "error").mockImplementation(() => {})
      fetchTrailerMock.mockRejectedValueOnce(new Error("network error"))

      const { result } = renderHook(() => useTrailer("media123"))

      act(() => {
        result.current.loadTrailer()
      })

      await waitFor(() => {
        expect(result.current.trailerState).toBe("unavailable")
      })

      expect(result.current.trailerKey).toBeNull()
      expect(errSpy).toHaveBeenCalledWith("Error fetching trailer:", expect.any(Error))
      errSpy.mockRestore()
    })
  })

  describe("abort on unmount", () => {
    it("aborts the in-flight signal and treats the AbortError as a no-op", async () => {
      const errSpy = vi.spyOn(console, "error").mockImplementation(() => {})
      let rejectTrailer!: (err: Error) => void
      let capturedSignal: AbortSignal | undefined
      fetchTrailerMock.mockImplementationOnce((_mediaId, signal) => {
        capturedSignal = signal
        return new Promise((_resolve, reject) => {
          rejectTrailer = reject
        })
      })

      const { result, unmount } = renderHook(() => useTrailer("media123"))

      act(() => {
        result.current.loadTrailer()
      })

      expect(result.current.trailerState).toBe("loading")
      expect(capturedSignal).toBeTruthy()

      // Unmounting must abort the in-flight fetch.
      unmount()

      expect(capturedSignal!.aborted).toBe(true)

      // Aborting a real controller does not auto-reject the vi.fn mock, so reject
      // it manually with an AbortError; the catch must treat it as a no-op.
      await act(async () => {
        const err = new Error("aborted")
        err.name = "AbortError"
        rejectTrailer(err)
      })

      expect(errSpy).not.toHaveBeenCalled()
      errSpy.mockRestore()
    })
  })

  describe("load-once", () => {
    it("issues no second fetch while non-idle", async () => {
      fetchTrailerMock.mockResolvedValue({ youtube_key: "abc123" })

      const { result } = renderHook(() => useTrailer("media123"))

      act(() => {
        result.current.loadTrailer()
      })

      await waitFor(() => {
        expect(result.current.trailerState).toBe("playing")
      })

      act(() => {
        result.current.loadTrailer()
      })

      expect(fetchTrailerMock).toHaveBeenCalledTimes(1)
    })
  })
})
