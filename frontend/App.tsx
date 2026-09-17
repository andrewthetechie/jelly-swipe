import React from "react"
import Main from "./Main"
import Header from "./Header"
import { apiFetch } from "./api"
import { RoomContextProvider } from "./RoomContextProvider" 
import { RoomSessionProvider } from "./RoomSessionProvider"
import { SSEContextProvider } from "./SSEContextProvider"
import FormError from "./FormError"

export default function App() {
    const [authError, setAuthError] = React.useState<string | null>(null)

    React.useEffect(() => {
        async function authBootstrap() {
            try {
                const res: Response = await apiFetch("/auth/jellyfin-use-server-identity", {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                })
                if (!res.ok) {
                    throw new Error(`Error authenticating server identity: ${res.status} ${res.statusText}`)
                }
            } catch (err) {
                console.error("Error authenticating server identity:", err)
                setAuthError("Couldn't sign in to your Jellyfin server. Check that the server is reachable, then reload the page.")
            }
        }

        authBootstrap()
    }, [])

    return (
        <RoomContextProvider>
            <SSEContextProvider>
                <RoomSessionProvider>
                    <FormError message={authError} />
                    <Header />
                    <Main />
                </RoomSessionProvider>
            </SSEContextProvider>
        </RoomContextProvider>
    )
}

