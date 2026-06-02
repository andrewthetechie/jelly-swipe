import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';
import App from './App';


const rootElement = document.getElementById('root') as HTMLElement;
const root = createRoot(rootElement);
root.render(<App />);
