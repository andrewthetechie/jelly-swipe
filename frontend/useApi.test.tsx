import { useApi } from "./useApi"
import { renderHook, waitFor } from "@testing-library/react"
import * as api from "./api"

describe("useApi - successful post", () => {
    it("calls doPost with the correct URL and data, and returns response", async () => {
        const { result } = renderHook(() => useApi())

        const fakeRes = {
            ok: true,
            status: 200,
            statusText: "OK",
            json: async () => ({ message: "Swipe recorded" }),
        }

        const postJsonSpy = vi.spyOn(api, "postJson").mockResolvedValue(fakeRes as unknown as Response)

        const res = await result.current.post("/room/1234/swipe", { media_id: "1", direction: "right" })

        expect(postJsonSpy).toHaveBeenCalledWith("/room/1234/swipe", { media_id: "1", direction: "right" }, {})
        expect(res).toEqual({ message: "Swipe recorded" })
    })

    it("resolves JSON and updates data state on success", async () => {
        const { result } = renderHook(() => useApi())

        const fakeRes = {
            ok: true,
            status: 200,
            statusText: "OK",
            json: async () => ({ message: "Swipe recorded" }),
        }

        vi.spyOn(api, "postJson").mockResolvedValue(fakeRes as unknown as Response)

        await result.current.post("/room/1234/swipe", { media_id: "1", direction: "right" })

        await waitFor(() => expect(result.current.data).toEqual({ message: "Swipe recorded" }))
    })

    it("updates isLoading state correctly during the request lifecycle", async () => {
        const { result } = renderHook(() => useApi())

        let resolveResp: (value: unknown) => void
        const pending = new Promise((res) => { resolveResp = res })

        const fakeRes = {
            ok: true,
            status: 200,
            statusText: "OK",
            json: async () => ({ message: "Swipe recorded" }),
        }

        // make postJson return a promise we control so we can observe isLoading=true
        const postJsonSpy = vi.spyOn(api, "postJson").mockImplementation(() => pending as unknown as Promise<Response>)

        const postPromise = result.current.post("/room/1234/swipe", { media_id: "1", direction: "right" })

        // isLoading should be true while the request is pending
        await waitFor(() => expect(result.current.isLoading).toBe(true))

        // resolve the pending fetch
        resolveResp!(fakeRes)
        await postPromise

        await waitFor(() => expect(result.current.isLoading).toBe(false))
        expect(postJsonSpy).toHaveBeenCalled()
    })
})

describe("useApi - error handling", () => {
    it("non-ok response sets error and returns null", async () => {
        const { result } = renderHook(() => useApi())

        const fakeRes = {
            ok: false,
            status: 500,
            statusText: "Err",
            json: async () => ({ error: "Failed" }),
        }

        vi.spyOn(api, "postJson").mockResolvedValue(fakeRes as unknown as Response)

        const res = await result.current.post("/room/1234/swipe", { media_id: "1", direction: "right" })

        expect(res).toBeNull()
        await waitFor(() => expect(result.current.error).toBeInstanceOf(Error))
    })

    it("network error sets error and returns null", async () => {
        const { result } = renderHook(() => useApi())

        vi.spyOn(api, "postJson").mockRejectedValue(new Error("Network error"))

        const res = await result.current.post("/room/1234/swipe", { media_id: "1", direction: "right" })

        expect(res).toBeNull()
        await waitFor(() => expect(result.current.error).toBeInstanceOf(Error))
    })
})