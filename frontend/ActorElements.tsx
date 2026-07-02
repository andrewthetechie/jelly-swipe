import React from "react"
import { JSX } from "react"
import type { CastMember } from "./types";
import logoImage from "./logo.png";
import sadLogo from "./sad.png"

interface ActorElementsProps {
    mediaId: string
}

const actorArray: CastMember[] = [
    {
        name: "Actor 1",
        character: "Character 1",
        profile_path: logoImage
    }, 
    {
        name: "Actor 2",
        character: "Character 1",
        profile_path: logoImage
    },
    {
        name: "Actor 3",
        character: "Character 1",
        profile_path: logoImage
    },
    {
        name: "Actor 4",
        character: "Character 1",
        profile_path: logoImage
    },
    {
        name: "Actor 5",
        character: "Character 1",
        profile_path: logoImage
    },
    {
        name: "Actor 6",
        character: "Character 1",
        profile_path: logoImage
    },
]

export default function ActorElements({ mediaId }: ActorElementsProps): JSX.Element {
    return (
        <>
            {actorArray.map((actor, index) => (
                <div key={`${mediaId}-${index}`} className="actor-card">
                    {actor.profile_path ? (
                        <img 
                            src={actor.profile_path} 
                            alt={`${actor.name} profile`} 
                            className="actor-image" 
                        />
                    ) : (
                        <img 
                            src={sadLogo} 
                            alt={`${actor.name} profile picture not available`}
                            className="actor-image" 
                        />
                    )}           
                    
                    <p className="actor-name">{actor.name}</p>
                </div>
            ))}
        </>
    )
}