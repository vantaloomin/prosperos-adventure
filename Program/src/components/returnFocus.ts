import { useEffect, useRef } from 'react'

/**
 * For a form that opens in place of the button that shows it: when the form closes, put focus back
 * on that button, unless focus has already moved somewhere else. Attach the returned ref to the button.
 */
export function useReturnFocus<T extends HTMLElement>(open: boolean) {
  const opener = useRef<T>(null)
  const wasOpen = useRef(open)
  useEffect(() => {
    if (wasOpen.current && !open && document.activeElement === document.body) opener.current?.focus()
    wasOpen.current = open
  }, [open])
  return opener
}
