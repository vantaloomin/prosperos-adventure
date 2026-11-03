/** A one-time line for the story after this page followed a world switch made in another tab or on another screen
 * (from Prospero's Companion #431): the page reloads into the new world, so the line waits in this tab's session
 * storage until the story shows it once. */
const KEY = 'adventure:arrival'

/** The line a page that followed a switch shows: where it went, when the world has a name. */
export function arrivalText(world?: string | null): string {
  return world ? `Now in ${world}. You switched worlds on another screen, so this one came too.`
    : 'Now in the world you opened on another screen. This one came too.'
}

/** Another tab or screen moved to another world, and this page came along (useFollowWorld, src/api.ts). */
export function followed(world?: string | null) {
  try { sessionStorage.setItem(KEY, arrivalText(world)) } catch { /* No line, nothing lost. */ }
}

/** The line, once. */
export function takeArrival(): string | null {
  try {
    const text = sessionStorage.getItem(KEY)
    sessionStorage.removeItem(KEY)
    return text
  } catch {
    return null
  }
}
