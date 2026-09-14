import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import './styles.css'

// React 19 uses createRoot from react-dom/client
createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)