/** Pure helpers for the city builder, kept apart from the components so they can be tested directly. */

export interface CityListing {
  id: string
  name: string
  region: string
  country: string
  setting: 'real' | 'fictional' | 'original'
  era: string
  summary: string
  basis: string
  counts: Record<'neighborhoods' | 'places' | 'colleges' | 'employers' | 'annual_events', number>
  builtin: boolean
  origin: 'builtin' | 'pack' | 'user'
  /** The city's shelf in city lists, decided by the server (dungeon/world/catalog.py `category`). */
  category?: string
  aliases?: string[]
  distribution: 'public' | 'private'
  /** What the server mended or added when it loaded the city; empty when it loaded as written. */
  import_notes?: string[]
  /** The world package the city belongs to (the travel map it is on), or null for a city on its own. */
  world?: string | null
  world_name?: string | null
  /** False for a road between towns: somewhere to pass through, not to live. */
  home?: boolean
}

/** The cities that belong where the user is: the built-in cities of the world `home` is in (or, for a city
 * on its own, only those on their own too), and every pack city and city of the user's own. All of them while
 * `home` is not known yet. */
export function citiesOfWorld<T extends Pick<CityListing, 'id' | 'origin' | 'world'>>(cities: T[], home?: string): T[] {
  if (!home) return cities
  const world = cities.find((city) => city.id === home)?.world ?? null
  return cities.filter((city) => city.origin !== 'builtin' || city.id === home || (city.world ?? null) === world)
}

/** The world a city's picker files it under: its world package, or 'custom' for a city outside them. */
export const CUSTOM_WORLD = 'custom'

interface Homed { id: string; name: string; world?: string | null; world_name?: string | null; home?: boolean }

export interface HomeWorld<T> { id: string; name: string; towns: T[] }

/** The worlds to pick first when choosing where someone lives, each with its towns A to Z: the featured cities'
 * worlds in featured order, then the other worlds by name, then Custom (cities outside the world packages). A road
 * between towns (`home` false) is never a town to live in. */
export function homeWorlds<T extends Homed>(cities: T[], featured: Pick<Homed, 'id'>[] = []): HomeWorld<T>[] {
  const worlds = new Map<string, HomeWorld<T>>()
  for (const city of [...cities].sort((a, b) => a.name.localeCompare(b.name))) {
    if (city.home === false) continue
    const id = city.world || CUSTOM_WORLD
    const world = worlds.get(id) ?? { id, name: id === CUSTOM_WORLD ? 'Custom' : city.world_name || id, towns: [] }
    world.towns.push(city)
    worlds.set(id, world)
  }
  const rank = (world: HomeWorld<T>) => {
    const index = featured.findIndex((city) => world.towns.some((town) => town.id === city.id))
    return world.id === CUSTOM_WORLD ? Infinity : index < 0 ? featured.length : index
  }
  return [...worlds.values()].sort((a, b) => rank(a) - rank(b) || a.name.localeCompare(b.name))
}

/** One of the user's own cities that no longer loads, with its saved definition. */
export interface BrokenCity { id: string; name: string; error: string; definition: unknown }

export interface PackReport { folders: string[]; loaded: { id: string; file: string; import_notes?: string[] }[]; errors: { file: string; error: string }[] }

/** Keys the server adds when it loads a city; they are not part of a definition. */
const DERIVED = ['data_version', 'builtin', 'origin', 'pack_file', 'revision', 'created_at', 'updated_at', 'import_notes']

export function definitionOf(city: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(Object.entries(city).filter(([key]) => !DERIVED.includes(key)))
}

export function slugify(text: string): string {
  return text.normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 80)
}

export type Parsed = { ok: true; value: Record<string, unknown> } | { ok: false; error: string }

/** Parse the editor's text as a city definition, with a readable message when it is not one. */
export function parseDefinition(text: string): Parsed {
  let value: unknown
  try {
    value = JSON.parse(text)
  } catch (error) {
    return { ok: false, error: `This is not valid JSON: ${error instanceof Error ? error.message : 'it could not be read'}.` }
  }
  if (!value || typeof value !== 'object' || Array.isArray(value)) return { ok: false, error: 'A city is a JSON object, starting with {.' }
  return { ok: true, value: value as Record<string, unknown> }
}

/** A release's featured cities (GET /world/featured); `new` while the app is on that release. */
export interface FeaturedCities<T = CityListing> { release: string; title: string; note: string; new: boolean; cities: (T & { new?: boolean })[] }

export type CityCategory = 'real' | 'other-eras' | 'fictional' | 'custom'

export const CATEGORIES: { id: CityCategory; title: string }[] = [
  { id: 'real', title: 'Real / Modern' }, { id: 'other-eras', title: 'Other Eras' },
  { id: 'fictional', title: 'Fictional' }, { id: 'custom', title: 'Custom' },
]

interface Shelved { name: string; category?: string }

/** The city's shelf; a city the server sent without one (an older server, or a scene's own city) counts as real. */
export function categoryOf(city: Shelved): CityCategory {
  return CATEGORIES.some((item) => item.id === city.category) ? city.category as CityCategory : 'real'
}

export interface Shelf<T> { id: CityCategory; title: string; cities: T[] }

/** Every shelf in order, each sorted by name. Empty shelves are kept so a list can say "None yet". */
export function shelveCities<T extends Shelved>(cities: T[]): Shelf<T>[] {
  const sorted = [...cities].sort((a, b) => a.name.localeCompare(b.name))
  return CATEGORIES.map((item) => ({ ...item, cities: sorted.filter((city) => categoryOf(city) === item.id) }))
}

const fold = (text: string) => text.normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase()

/** Whether a city matches what was typed into the city search: its name, other names, region or country. */
export function matchesCity(city: Pick<CityListing, 'name' | 'region' | 'country' | 'aliases'>, query: string): boolean {
  const wanted = fold(query.trim())
  return !wanted || [city.name, city.region, city.country, ...(city.aliases ?? [])].some((text) => fold(text).includes(wanted))
}

const SETTINGS: Record<CityListing['setting'], string> = { real: 'Real city', fictional: 'Fictional setting', original: 'Original setting' }

/** "Real city · modern · 21 neighborhoods, 124 places" */
export function cityFacts(city: CityListing): string {
  const plural = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`
  return [SETTINGS[city.setting], city.era,
    `${plural(city.counts.neighborhoods, 'neighborhood', 'neighborhoods')}, ${plural(city.counts.places, 'place', 'places')}`].join(' · ')
}

/** A file name for an exported city. */
export function exportName(id: string): string {
  return `${slugify(id) || 'city'}.json`
}

/** Notes that say the same about several records ("Bluebird Diner: filled in cost as '$'.") as one line naming
 * them all, where the first of them was; every other note as it is. */
export function groupNotes(notes: string[]): string[] {
  const split = notes.map((note) => /^([^:]{1,80}): (.+)$/.exec(note))
  const named = new Map<string, string[]>()
  split.forEach((found) => { if (found) named.set(found[2], [...(named.get(found[2]) ?? []), found[1]]) })
  const done = new Set<string>()
  return notes.flatMap((note, index) => {
    const found = split[index]
    const names = found ? named.get(found[2])! : []
    if (!found || names.length < 2) return [note]
    if (done.has(found[2])) return []
    done.add(found[2])
    const shown = names.length > 6 ? `${names.slice(0, 5).join(', ')} and ${names.length - 5} more` : `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`
    return [`${shown}: ${found[2]}`]
  })
}
