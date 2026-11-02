/** A time zone as a person reads it: "Los Angeles · Pacific Time (UTC−08:00)", with the IANA id kept for saving. */
export interface Zone { id: string; label: string; offset: number; search: string; named: string }

/** Zones most people look for, shown above the rest when the browser lists them (some list Kolkata as Calcutta). */
export const COMMON_ZONES = ['America/Los_Angeles', 'America/Denver', 'America/Chicago', 'America/New_York', 'America/Sao_Paulo',
  'Europe/London', 'Europe/Paris', 'Europe/Berlin', 'Africa/Johannesburg', 'Europe/Moscow', 'Asia/Dubai', 'Asia/Kolkata', 'Asia/Calcutta',
  'Asia/Shanghai', 'Asia/Tokyo', 'Australia/Sydney', 'Pacific/Auckland', 'UTC']

/** Old city names some browsers still list, shown as the city is called now. */
const RENAMED: Record<string, string> = { Calcutta: 'Kolkata', Saigon: 'Ho Chi Minh City', Kiev: 'Kyiv', Rangoon: 'Yangon', Katmandu: 'Kathmandu' }

function part(id: string, style: 'longOffset' | 'longGeneric', at: Date): string {
  try {
    return new Intl.DateTimeFormat('en-US', { timeZone: id, timeZoneName: style }).formatToParts(at).find((item) => item.type === 'timeZoneName')?.value ?? ''
  } catch { return '' }
}

/** "GMT+05:30" (or "GMT") to minutes east of UTC. */
function minutes(offset: string): number {
  const found = /([+-])(\d{1,2})(?::(\d{2}))?/.exec(offset)
  return found ? (found[1] === '-' ? -1 : 1) * (Number(found[2]) * 60 + Number(found[3] ?? 0)) : 0
}

/** "UTC+05:30", "UTC−08:00", "UTC". */
export function offsetText(total: number): string {
  if (total === 0) return 'UTC'
  const size = Math.abs(total)
  return `UTC${total < 0 ? '−' : '+'}${String(Math.floor(size / 60)).padStart(2, '0')}:${String(size % 60).padStart(2, '0')}`
}

/** One zone as a person reads it, its offset as of `at` (so summer time shows when it is on). */
export function zoneOf(id: string, at = new Date()): Zone {
  const city = id === 'UTC' ? 'UTC' : (id.split('/').pop() ?? id).replace(/_/g, ' ')
  const place = RENAMED[city] ?? city
  const region = id.includes('/') ? id.split('/')[0].replace(/_/g, ' ') : ''
  const offset = minutes(part(id, 'longOffset', at))
  const generic = part(id, 'longGeneric', at)
  const name = generic && !generic.startsWith('GMT') && generic !== place ? ` · ${generic}` : ''
  const label = `${place}${name} (${offsetText(offset)})`
  const named = label.toLowerCase().replace(/−/g, '-')
  return { id, label, offset, named, search: `${named} ${region} ${city} ${id}`.toLowerCase() }
}

/** Every zone, west to east then by name; `extra` adds one the browser doesn't list (a saved one, say). */
export function allZones(ids: string[], extra: (string | null | undefined)[] = [], at = new Date()): Zone[] {
  const unique = [...new Set([...ids, ...extra.filter((item): item is string => !!item)])]
  return unique.map((id) => zoneOf(id, at)).sort((a, b) => a.offset - b.offset || a.label.localeCompare(b.label))
}

/** The common zones among `zones`, in the same west-to-east order. */
export function commonZones(zones: Zone[]): Zone[] {
  return zones.filter((zone) => COMMON_ZONES.includes(zone.id))
}

/** The zones a search finds: every word in the city, region, zone name, id or offset ("tokyo", "pacific", "+05:30").
 * Those found by what the list shows come first, then those found only by region or id. */
export function findZones(zones: Zone[], query: string): Zone[] {
  const words = query.toLowerCase().replace(/−/g, '-').split(/\s+/).filter(Boolean)
  if (!words.length) return zones
  const found = zones.filter((zone) => words.every((word) => zone.search.includes(word)))
  const shown = (zone: Zone) => words.every((word) => zone.named.includes(word))
  return [...found.filter(shown), ...found.filter((zone) => !shown(zone))]
}
