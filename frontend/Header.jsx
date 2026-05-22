import React from 'react';
import nameLogo from './assets/name-logo.png';

export default function Header() {
    return (
        <header className="app-header">
            <img src={nameLogo} alt="Jelly-Swipe logo" className="app-logo" />
        </header>
    );
}