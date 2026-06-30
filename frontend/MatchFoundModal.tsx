import React from "react"
import logo from "./assets/logo.png"
import moanaPoster from "./assets/moana-poster.jpg"
import type { JSX } from "react"

interface MatchFoundModalProps {
    onClick: () => void
}

export default function MatchFoundModal({ onClick }: MatchFoundModalProps): JSX.Element {
    return (
        <div className="modal">
            <div className="modal-inner">
                <img src={logo} className="match-logo" />
                <h2>It's a match!</h2>
                <img src={moanaPoster} className="match-poster" />
                <h3 className="match-title">Moana</h3>
                <div className="card-item-info match-info">
                    <div className="card-item-score">IMDb 7.6</div>
                    <div className="card-item-runtime">1h 47m</div>
                    <div className="card-item-year">2016</div>
                </div>
                <button className="modal-button">Open in Jellyfin</button>
                <button className="modal-button" onClick={onClick}>Keep Swiping</button>
            </div>
        </div>
    )
}