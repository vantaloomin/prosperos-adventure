/** The town map (dungeon/townmap.py) as the Town widget draws it: what the server sends, and the sums for drawing it. */

export type Point = [number, number]
export interface TownThing { id: string; name: string; kind: string; what?: string; summary?: string }
/** A patch of the map. Open ground holding a place the character has not found is `hidden`: looking finds it. */
export interface TownPatch { id: number; kind: 'town' | 'country' | 'square' | 'open' | 'water'; neighborhood: string | null; polygon: Point[]; place: TownThing | null; hidden?: boolean }
/** A lot: one of the town's own places the character knows of, or blank until looked at (`found`, then kept). A place
 *  they have not found yet is blank too, until they look or hear of it. */
export interface TownLot { id: string; neighborhood: string; front: boolean; place: TownThing | null; found?: TownThing | null; polygon: Point[] }
export interface TownMap {
  town: string; name: string; style: 'ink' | 'street' | 'floor'; walls: boolean; size: number
  patches: TownPatch[]; streets: [Point, Point][]; roads: Point[][]
  water: { name: string; width: number; points: Point[] }[]
  lots: TownLot[]; districts: { id: string; name: string; label: Point; patches: number[] }[]
  exits: { id: string; name: string; at: Point | null }[]; square: number; border: [Point, Point][]
  here: { place: string; neighborhood: string | null }
}

/** How far in the map can be zoomed: 1 shows the whole map, each step halves what is shown. */
export const ZOOMS = [1, 2, 4]

export function middle(polygon: Point[]): Point {
  const n = polygon.length || 1
  return [polygon.reduce((sum, [x]) => sum + x, 0) / n, polygon.reduce((sum, [, y]) => sum + y, 0) / n]
}

export function points(polygon: Point[]): string {
  return polygon.map(([x, y]) => `${x},${y}`).join(' ')
}

/** Where the character is on the map: their place's lot or open ground, else their neighborhood, else the square. */
export function whereOnMap(town: TownMap): Point {
  const lot = town.lots.find((found) => (found.place ?? found.found)?.id === town.here.place)
  if (lot) return middle(lot.polygon)
  const ground = town.patches.find((patch) => patch.place?.id === town.here.place)
  if (ground) return middle(ground.polygon)
  const district = town.districts.find((found) => found.id === town.here.neighborhood)
  if (district) return district.label
  return middle(town.patches.find((patch) => patch.id === town.square)?.polygon ?? [[0, 0]])
}

/** The part of the map shown at a zoom, centred on `on` but never past the map's edge. The whole town is the
 *  middle of the map, with the country just around it. */
export function viewBox(town: TownMap, zoom: number, on: Point): [number, number, number, number] {
  const whole = town.size * 1.5
  const span = whole / zoom
  const clamp = (value: number) => Math.max(-whole / 2, Math.min(whole / 2 - span, value - span / 2))
  return [clamp(on[0]), clamp(on[1]), span, span]
}

/** The town's named places, the lots and open ground that hold one, by name. */
export function namedPlaces(town: TownMap): { thing: TownThing; at: Point; open: boolean }[] {
  return [
    ...town.patches.filter((patch) => patch.place).map((patch) => ({ thing: patch.place!, at: middle(patch.polygon), open: true })),
    ...town.lots.filter((lot) => lot.place ?? lot.found).map((lot) => ({ thing: (lot.place ?? lot.found)!, at: middle(lot.polygon), open: false })),
  ].sort((a, b) => a.thing.name.localeCompare(b.thing.name))
}

/** What a place is, in a word or two for its label on the map. */
export function kindName(thing: TownThing): string {
  if (thing.what === 'employer') return 'workplace'
  if (thing.what === 'college') return 'college'
  return thing.kind
}

/** A lot's look: a named place's lot stands out, one looked at a little, and yours and the one picked most. */
export function lotClass(lot: TownLot, town: TownMap, picked?: string): string {
  const id = (lot.place ?? lot.found)?.id
  return ['town-lot', lot.place && 'named', lot.found && 'found', id && id === town.here.place && 'here', id && id === picked && 'picked']
    .filter(Boolean).join(' ')
}
