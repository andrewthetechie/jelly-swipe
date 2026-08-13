import React from "react"
import Main from "./Main"
import Header from "./Header"
import { apiFetch } from "./api"
import { RoomContextProvider } from "./RoomContextProvider" 
import { SSEContextProvider } from "./SSEContextProvider"

export default function App() {
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
            }
        }

        authBootstrap()
    }, [])

    return (
        <RoomContextProvider>
            <SSEContextProvider>
                <Header />
                <Main />
            </SSEContextProvider>
        </RoomContextProvider>
    )
}

