import React from "react"
import CardItemView from "./CardItemView"
import { useRoomContext } from "./RoomContextProvider"
import { apiFetch } from "./api"
import type { JSX } from "react"
import type { CardItem } from './types'
import type { CardDeck } from './types'


export default function SwipePage( { cardDeck }: { cardDeck: CardDeck } ): JSX.Element {
    const [dragX, setDragX] = React.useState<number>(0)
    const { currentRoomCode, setCurrentRoomCode } = useRoomContext()

    const rightOpacity: number = 
        dragX > 20
            ? Math.min(Math.abs(dragX) / 200, 1)
            : 0
    const leftOpacity: number = 
        dragX < -20
            ? Math.min(Math.abs(dragX) / 200, 1)
            : 0
    const visibleCards = cardDeck.slice(0, 5).reverse()

    async function handleEndSession() {
        try {
            const res: Response = await apiFetch(`/room/${currentRoomCode}/quit`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
            })
            if (!res.ok) {
                throw new Error(`Error quitting room: ${res.status} ${res.statusText}`)
            }
            
            const quitRoomResponse: { status: string } = await res.json()
            console.log("Session ended", quitRoomResponse)
            setCurrentRoomCode(null)
            
        } catch (err) {
            console.error("Error quitting room:", err)
        }
    }

    return (
        <>
            <div className="swipe-header">
                <div className="mode-badge">Solo</div>
                <button className="show-watched hide-watched">Show Watched</button>
                <div className="genres">Genres</div>
            </div>

            <div className="swipe-main">
                <div className="swipe-deck">
                    {visibleCards.map((cardItem: CardItem, index: number) => (
                        <CardItemView 
                            key={cardItem.media_id}
                            cardItem={cardItem}
                            isTopCard={index === visibleCards.length - 1}
                            setDragX={setDragX}
                            zIndex={index}
                        />
                    ))}
                </div>
                
                

                <button className="undo-button">Undo</button>
                <p className="card-item-instructions">Tap poster for full details</p>
            </div>

            <div className="swipe-footer">
                <button className="end-session" onClick={handleEndSession}>End Session</button>
                <button className="shortlist">Shortlist</button>
            </div>

            <div className="glow glow-left" style={{ opacity: leftOpacity }}></div>
            <div className="glow glow-right" style={{ opacity: rightOpacity }}></div>
        </>
    )
}