import { screen, render, waitFor } from "@testing-library/react"
import App from "./App"
import { apiFetch } from "./api"

vi.mock("./api", () => ({
  apiFetch: vi.fn(),
}))

const apiFetchMock = vi.mocked(apiFetch)

beforeEach(() => {
  vi.clearAllMocks()
})

describe("App - auth bootstrap", () => {
  it("renders an alert when auth bootstrap fails", async () => {
    apiFetchMock.mockResolvedValue({
      ok: false,
      status: 500,
      statusText: "Server Error",
    } as Response)

    render(<App />)

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Couldn't sign in to your Jellyfin server. Check that the server is reachable, then reload the page.",
    )
  })

  it("renders nothing extra on success", async () => {
    apiFetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      statusText: "OK",
    } as Response)

    render(<App />)

    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenCalledOnce()
    })

    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
  })
})
