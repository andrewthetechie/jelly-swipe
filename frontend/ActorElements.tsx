import React from "react"
import { JSX } from "react"
import type { CastMember } from "./types";
import useMovieCast from "./useMovieCast";
import logoImage from "./assets/logo.png";
import sadLogo from "./assets/sad.png"

interface ActorElementsProps {
    mediaId: string
}

export default function ActorElements({ mediaId }: ActorElementsProps): JSX.Element {
    const { cast, isLoading, error } = useMovieCast(mediaId)
    
    if (isLoading) {
        return (
            <div className="card-item-cast" data-testid="actor-elements">
                <h3 className="cast-loading">Loading cast...</h3>
            </div>
        )
    } else if (!cast.length || error) {
        return (
            <div className="card-item-cast" data-testid="actor-elements">
                <h3 className="cast-loading">Unable to load cast</h3>
            </div>
        )
    } else {
        return (
            <div className="card-item-cast" data-testid="actor-elements">
            {cast.map((actor, index) => (
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
            </div>
        )
    }
    
}