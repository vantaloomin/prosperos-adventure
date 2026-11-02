import { useEffect } from 'react'

// A user folder at the start of a path: C:\Users\name, /Users/name (Mac) or /home/name (Linux).
const HOME = /^(?:[A-Za-z]:)?([\\/])(?:Users|home)\1[^\\/]+(?=[\\/]|$)/i

/** A path as shown on screen, with the user's home folder written as ~ so screenshots don't carry their name.
 * Display only: buttons and saved settings keep the real path. */
export function shownPath(path: string): string {
  return path.replace(HOME, '~')
}

/** Asks again whenever the app window gets focus back, for lists of files the user adds outside the app
 * (React Query only notices a hidden tab coming back, not a switch from File Explorer or Finder). */
export function useRefetchOnFocus(refetch: () => unknown, enabled = true) {
  useEffect(() => {
    if (!enabled) return
    const again = () => { void refetch() }
    window.addEventListener('focus', again)
    return () => window.removeEventListener('focus', again)
  }, [refetch, enabled])
}
