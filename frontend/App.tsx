import React from "react"
import Main from "./Main"
import Header from "./Header"
import { RoomContextProvider } from "./RoomContextProvider" 
import { SSEContextProvider } from "./SSEContextProvider"

export default function App() {


    return (
        <RoomContextProvider>
            <SSEContextProvider>
                <Header />
                <Main />
            </SSEContextProvider>
        </RoomContextProvider>
    )
}

