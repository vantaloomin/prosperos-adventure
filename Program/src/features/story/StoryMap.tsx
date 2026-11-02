import type { MapHex, StoryMap as TravelMap } from '../../types'
import { EntityName } from './EntityCard'

const SIZE = 300
const PAD = 28
/** Hexes either way of where you are that the hex map shows; the rest of what you have seen is off its edge. */
const REACH = 9
const SIDE = 9
const ROOT3 = Math.sqrt(3)
const TERRAIN_NAMES: Record<MapHex['terrain'], string> = {
  water: 'open water', plains: 'open country', forest: 'forest', hills: 'hills', mountains: 'mountains', waste: 'waste', marsh: 'marsh',
}
const COMPASS = ['north', 'north-east', 'east', 'south-east', 'south', 'south-west', 'west', 'north-west']

/** A hex's centre on the screen, flat-topped. */
function centre(q: number, r: number): [number, number] {
  return [SIDE * 1.5 * q, SIDE * ROOT3 * (r + q / 2)]
}

function corners(x: number, y: number): string {
  return Array.from({ length: 6 }, (_, i) => {
    const angle = Math.PI / 3 * i
    return `${(x + SIDE * Math.cos(angle)).toFixed(1)},${(y + SIDE * Math.sin(angle)).toFixed(1)}`
  }).join(' ')
}

function distance(a: { q: number; r: number }, b: { q: number; r: number }): number {
  return (Math.abs(a.q - b.q) + Math.abs(a.r - b.r) + Math.abs(a.q + a.r - b.q - b.r)) / 2
}

/** Which way a hex lies from another, as a compass word. */
function bearing(from: { q: number; r: number }, to: { q: number; r: number }): string {
  const [x1, y1] = centre(from.q, from.r), [x2, y2] = centre(to.q, to.r)
  const angle = (Math.atan2(x2 - x1, y1 - y2) * 180 / Math.PI + 360) % 360
  return COMPASS[Math.round(angle / 45) % 8]
}

/** The travel map as far as your character knows it (dungeon/travel.py): where you are, where you have been, the
 *  places you have heard of and the roads between them. On a hex crawl (dungeon/hexes.py) it is the land around you,
 *  hex by hex, with the rest still dark. Setting out puts the line in the box to send. */
export function StoryMap({ map, open, onTravel, onLine }: { map: TravelMap | null; open?: boolean; onTravel: (name: string) => void; onLine?: (text: string) => void }) {
  if (!map?.places.length && !map?.hexes?.length) return null
  const names = new Map(map.places.map((place) => [place.id, place.name]))
  const where = whereText(map)
  return (
    <details className="story-people story-map" open={open}>
      <summary>Map{where ? ` (${where})` : ''}</summary>
      {map.hexes?.length && map.at
        ? <HexMap hexes={map.hexes} at={map.at} names={names} onTravel={onTravel} onLine={onLine} />
        : <RoadMap map={map} />}
      <ul className="map-places">
        {map.places.filter((place) => !place.here).map((place) => <li key={place.id}>
          <span><EntityName entity={{ kind: 'place', id: place.id }}>{place.name}</EntityName>{place.visited ? '' : ' (heard of)'}</span>
          <button type="button" className="text-button" onClick={() => onTravel(place.name)}>Set out</button>
        </li>)}
      </ul>
    </details>
  )
}

/** Where the summary says you are: the place, out in the wild, or lost. */
function whereText(map: TravelMap): string | undefined {
  const here = map.places.find((place) => place.here)?.name
  if (!map.at) return here
  return map.at.lost ? 'lost' : here ?? 'out in the wild'
}

function RoadMap({ map }: { map: TravelMap }) {
  const xs = map.places.map((place) => place.x), ys = map.places.map((place) => place.y)
  const [left, top] = [Math.min(...xs), Math.min(...ys)]
  const span = Math.max(Math.max(...xs) - left, Math.max(...ys) - top, 0.01)
  const at = (x: number, y: number) => [PAD + (x - left) / span * (SIZE - 2 * PAD), PAD + (y - top) / span * (SIZE - 2 * PAD)]
  const where = new Map(map.places.map((place) => [place.id, at(place.x, place.y)]))
  const height = Math.max(...map.places.map((place) => where.get(place.id)![1])) + PAD
  const here = map.places.find((place) => place.here)
  return (
    <svg viewBox={`0 0 ${SIZE} ${height}`} role="img" aria-label={`Map: you are at ${here?.name ?? 'an unknown place'}.`}>
      {map.roads.map((road) => {
        const [x1, y1] = where.get(road.from)!, [x2, y2] = where.get(road.to)!
        return <line key={`${road.from}-${road.to}`} x1={x1} y1={y1} x2={x2} y2={y2}
          className={`map-road danger-${road.danger}`}><title>{`${road.terrain}: ${road.hours} hours on foot`}</title></line>
      })}
      {map.places.map((place) => {
        const [x, y] = where.get(place.id)!
        return <g key={place.id} className={place.here ? 'map-place here' : place.visited ? 'map-place visited' : 'map-place'}>
          <circle cx={x} cy={y} r={place.here ? 6 : 4} />
          <text x={x} y={y - 9} textAnchor="middle">{place.name}</text>
        </g>
      })}
    </svg>
  )
}

/** The hexes around you, coloured by their land; a click on one puts setting out for it, or heading its way, in the
 *  box. Lost, the ring marks where you believe you are. */
function HexMap({ hexes, at, names, onTravel, onLine }: { hexes: MapHex[]; at: NonNullable<TravelMap['at']>; names: Map<string, string>; onTravel: (name: string) => void; onLine?: (text: string) => void }) {
  const near = hexes.filter((hex) => distance(hex, at) <= REACH)
  const points = near.map((hex) => centre(hex.q, hex.r))
  const left = Math.min(...points.map(([x]) => x)) - SIDE - 2, top = Math.min(...points.map(([, y]) => y)) - SIDE - 2
  const width = Math.max(...points.map(([x]) => x)) - left + SIDE + 2, height = Math.max(...points.map(([, y]) => y)) - top + SIDE + 2
  const [hereX, hereY] = centre(at.q, at.r)
  const seenAt = new Set(near.map((hex) => `${hex.q},${hex.r}`))
  const pick = (hex: MapHex) => {
    const name = hex.place ? names.get(hex.place) : hex.site
    if (name) onTravel(name)
    else if (hex.q !== at.q || hex.r !== at.r) onLine?.(`I head ${bearing(at, hex)}.`)
  }
  return (
    <svg className="hex-map" viewBox={`${left.toFixed(1)} ${top.toFixed(1)} ${width.toFixed(1)} ${height.toFixed(1)}`} role="img"
      aria-label={`Map of the land around you${at.lost ? ', where you believe you are' : ''}.`}>
      {near.map((hex) => {
        const [x, y] = centre(hex.q, hex.r)
        const label = hex.place ? names.get(hex.place) : hex.site
        return <g key={`${hex.q},${hex.r}`} className={`map-hex terrain-${hex.terrain}${hex.visited ? ' visited' : ''}`}
          onClick={() => pick(hex)}>
          <polygon points={corners(x, y)}>
            <title>{[label, hex.road ? 'a road' : null, hex.river?.name, TERRAIN_NAMES[hex.terrain]].filter(Boolean).join(', ')}</title>
          </polygon>
          {hex.road && <circle className="map-hex-road" cx={x} cy={y} r={1.6} />}
          {hex.place && <circle className="map-hex-place" cx={x} cy={y} r={3.2} />}
          {hex.site && !hex.place && <rect className="map-hex-site" x={x - 2.4} y={y - 2.4} width={4.8} height={4.8} transform={`rotate(45 ${x} ${y})`} />}
        </g>
      })}
      {near.filter((hex) => hex.river?.down).map((hex) => {
        // Each river hex runs to the next one downstream; drawn only where you have seen both.
        const [dq, dr] = hex.river!.down!
        if (!seenAt.has(`${dq},${dr}`)) return null
        const [x1, y1] = centre(hex.q, hex.r), [x2, y2] = centre(dq, dr)
        return <line key={`river-${hex.q},${hex.r}`} className="map-hex-river" x1={x1} y1={y1} x2={x2} y2={y2}
          strokeWidth={1 + Math.sqrt(hex.river!.flow) * 2.5}><title>{hex.river!.name}</title></line>
      })}
      {near.filter((hex) => hex.place || hex.site).map((hex) => {
        const [x, y] = centre(hex.q, hex.r)
        return <text key={`label-${hex.q},${hex.r}`} className="map-hex-label" x={x} y={y - SIDE * 0.65} textAnchor="middle">
          {hex.place ? names.get(hex.place) : hex.site}</text>
      })}
      <circle className={`map-hex-here${at.lost ? ' lost' : ''}`} cx={hereX} cy={hereY} r={SIDE * 0.75}>
        <title>{at.lost ? 'Where you believe you are' : 'You are here'}</title>
      </circle>
    </svg>
  )
}
