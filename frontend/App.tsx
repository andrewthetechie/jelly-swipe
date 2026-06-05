import React from "react"
import Main from "./Main"
import Header from "./Header"
import { RoomContextProvider } from "./RoomContextProvider" 

export default function App() {


    return (
        <RoomContextProvider>
            <Header />
            <Main />
        </RoomContextProvider>
    )
}

