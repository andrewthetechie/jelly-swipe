import React from "react";
import logoImage from "./logo.png";

const actorArray = [
    {
        name: "Actor 1",
        image: logoImage
    }, 
    {
        name: "Actor 2",
        image: logoImage
    },
    {
        name: "Actor 3",
        image: logoImage
    },
    {
        name: "Actor 4",
        image: logoImage
    },
    {
        name: "Actor 5",
        image: logoImage
    },
    {
        name: "Actor 6",
        image: logoImage
    },
]

export const actorElements = actorArray.map((actor, index) => (
    <div key={index} className="actor-card">
        <img src={actor.image} alt={`${actor.name} profile`} className="actor-image" />
        <p className="actor-name">{actor.name}</p>
    </div>
))