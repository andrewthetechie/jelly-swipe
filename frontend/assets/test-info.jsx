import React from "react";
import logoImage from "./logo.png";

export const matchListSample = [
    {
        title: "Moana",
        thumb: "./assets/moana-poster.jpg",
        media_id: "1",
        media_type: "movie",
        deep_link: "#",
        rating: "5.7",
        duration: "1h 47m",
        year: 2016,
    },
    {
        title: "Moana 2",
        thumb: "./assets/moana-poster.jpg",
        media_id: "2",
        media_type: "movie",
        deep_link: "#",
        rating: "5.7",
        duration: "1h 47m",
        year: 2016,
    },
    {
        title: "Moana 3",
        thumb: "./assets/moana-poster.jpg",
        media_id: "3",
        media_type: "movie",
        deep_link: "#",
        rating: "5.7",
        duration: "1h 47m",
        year: 2016,
    },
    {
        title: "Moana 4",
        thumb: "./assets/moana-poster.jpg",
        media_id: "4",
        media_type: "movie",
        deep_link: "#",
        rating: "5.7",
        duration: "1h 47m",
        year: 2016,
    }

]

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