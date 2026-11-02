import type { DebugTime } from './types'

/**
 * The app's time, which is the PC's real time unless debug time (Settings > Developer) moved it ahead or
 * made it run faster (dungeon/debug_time.py). Anything comparing against times the server wrote,
 * such as what day it is in the story, reads it here.
 */
let synced = { app: 0, local: 0, speed: 1, active: false }

export function syncAppClock(status: Pick<DebugTime, 'active' | 'now' | 'speed'>) {
  synced = { app: Date.parse(status.now), local: Date.now(), speed: status.speed, active: status.active }
}

export function appNow(): number {
  return synced.active ? synced.app + (Date.now() - synced.local) * synced.speed : Date.now()
}

/** Real milliseconds until `appMs` of app time have passed. */
export function realDelay(appMs: number): number {
  return synced.active ? appMs / synced.speed : appMs
}
