import { createRoot } from 'react-dom/client';
import './style.css';
import "@fontsource-variable/orbitron";
import "@fontsource-variable/raleway";
import App from './App';


const rootElement = document.getElementById('root') as HTMLElement;
const root = createRoot(rootElement);
root.render(<App />);
