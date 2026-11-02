import { useEffect, useSyncExternalStore } from 'react'
import { useWorkspaceSettings } from '../../workspace'
import { applyLook, readLook } from './deviceLook'
import { paletteStyles, shownScheme } from './palette'

const LIGHT_QUERY = '(prefers-color-scheme: light)'
// The last colors shown, read by the script in index.html before the first paint so a Paper user never sees a dark frame.
const CACHE = 'dungeon-colors'
const BAR = { ink: '#191816', paper: '#f4f0e8' }

function subscribe(change: () => void) {
  const query = window.matchMedia(LIGHT_QUERY)
  query.addEventListener('change', change)
  return () => query.removeEventListener('change', change)
}

/** Whether the computer is set to light, kept up to date when it changes (a switch to dark at sunset, say). */
function useComputerLight() {
  return useSyncExternalStore(subscribe, () => window.matchMedia(LIGHT_QUERY).matches, () => false)
}

/** Puts the saved colors and this device's look on the page root, so dialogs and menus outside the app shell follow
 * them too, and remembers the colors for the next start. */
export function useAppColors() {
  const settings = useWorkspaceSettings().data
  const light = useComputerLight()
  const scheme = shownScheme(settings, light)
  const palette = settings?.custom_palette
  useEffect(() => {
    if (!settings) return  // Until they load, the colors the page started with stay.
    const root = document.documentElement
    root.dataset.theme = scheme
    const styles = scheme === 'custom' ? paletteStyles(palette) : {}
    for (const [name, value] of Object.entries(styles)) root.style.setProperty(name, value)
    const bar = scheme === 'paper' ? BAR.paper : styles['--canvas'] ?? BAR.ink
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', bar)
    try { localStorage.setItem(CACHE, JSON.stringify({ scheme, styles, bar, system: settings.theme === 'system' })) } catch { /* the next start shows Ink first */ }
    return () => { for (const name of Object.keys(styles)) root.style.removeProperty(name) }
  }, [settings, scheme, palette])
  useEffect(() => applyLook(readLook()), [])
}
