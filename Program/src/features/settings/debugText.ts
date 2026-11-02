/** Words for debug time (Settings > Developer and the banner shown while it is on). */

export const SPEED_LABELS: Record<number, string> = {
  1: 'Normal speed',
  10: '10× (an hour every 6 minutes)',
  60: '60× (an hour a minute)',
  360: '360× (6 hours a minute)',
  1440: '1440× (a day a minute)',
}

/** A weekday, date and time in the user's timezone, falling back to this browser's. */
export function formatAppTime(iso: string, zone?: string): string {
  const options: Intl.DateTimeFormatOptions = { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }
  try {
    return new Intl.DateTimeFormat(undefined, { ...options, timeZone: zone }).format(new Date(iso))
  } catch {
    return new Intl.DateTimeFormat(undefined, options).format(new Date(iso))
  }
}

export function bannerText(status: { now: string; speed: number; jumping: { to: string; done: number } | null }, zone?: string): string {
  if (status.jumping) return `Debug time: jumping ahead to ${formatAppTime(status.jumping.to, zone)} (${Math.round(status.jumping.done * 100)}%).`
  const speed = status.speed > 1 ? `, running ${status.speed}× fast` : ''
  return `Debug time: it is ${formatAppTime(status.now, zone)} in the app${speed}. Return to real time in Settings > Developer.`
}
