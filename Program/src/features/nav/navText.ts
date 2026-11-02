/** Every view the address can name (src/workspace.ts View). */
export function isView(id: string): boolean {
  return id === 'story' || id === 'worlds' || id === 'settings' || id.startsWith('settings/')
}

/** Whether a nav button is lit. */
export function navCurrent(id: string, view: string): boolean {
  if (id === 'settings') return view === 'settings' || view.startsWith('settings/')
  return view === id
}
