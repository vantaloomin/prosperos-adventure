import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import '@fontsource/ibm-plex-sans/400.css'
import '@fontsource/ibm-plex-sans/500.css'
// Italic and bold faces too: the root turns font synthesis off, so *italics* and **bold** in model text need real faces.
import '@fontsource/ibm-plex-sans/400-italic.css'
import '@fontsource/literata/400.css'
import '@fontsource/literata/400-italic.css'
import '@fontsource/literata/700.css'
import '@fontsource/literata/700-italic.css'
import '@fontsource/atkinson-hyperlegible/latin-400.css'
import '@fontsource/atkinson-hyperlegible/latin-400-italic.css'
import '@fontsource/atkinson-hyperlegible/latin-700.css'
import '@fontsource/atkinson-hyperlegible/latin-700-italic.css'
import './styles.css'
import App from './App'

const client = new QueryClient({ defaultOptions: { queries: { staleTime: 10_000, retry: 1, refetchOnWindowFocus: false } } })
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode><QueryClientProvider client={client}><App /></QueryClientProvider></React.StrictMode>,
)

// Lets the browser install the app (public/sw.js). It caches nothing.
if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(() => undefined)
