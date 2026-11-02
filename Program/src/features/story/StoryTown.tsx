import { useState, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api'
import { kindName, lotClass, middle, namedPlaces, points, viewBox, whereOnMap, ZOOMS, type Point, type TownMap, type TownThing } from './town'

interface Picked { thing: TownThing; at: Point }

interface TownProps {
  where: string; open?: boolean; onLine?: (text: string) => void
  /** Going there now, with no line to send (the scene bar's Go somewhere else); without it, going puts the line in the box. */
  onGo?: (thing: TownThing) => void
  /** What shows instead when there is no street map here. */
  empty?: ReactNode
}

/** The street map of the town the story is in (dungeon/townmap.py): its neighborhoods, streets, main roads, water
 *  and buildings, laid out by code from the town's data and the campaign's seed. Only the places the character knows
 *  of are named: the rest are blank until looked at, passed or heard of. A place on it can be looked at and gone to; going puts the line in the box, or with `onGo` goes now. Zoomed in, the map follows where you are or what
 *  you picked. */
export function StoryTown({ where, open, onLine, onGo, empty }: TownProps) {
  const key = ['story-town', where]
  const client = useQueryClient()
  const town = useQuery({ queryKey: key, queryFn: () => api<{ town: TownMap | null }>('/story/town') })
  const [zoom, setZoom] = useState(1)
  const [picked, setPicked] = useState<Picked | null>(null)
  const [error, setError] = useState('')
  const map = town.data?.town
  if (!map) return town.isSuccess ? empty ?? <p className="subtle">There is no street map out here.</p> : null
  const places = namedPlaces(map)
  // A blank building is decided when you look at it, and kept; a place not found yet is found.
  const look = async (id: string, polygon: Point[]) => {
    setError('')
    try {
      const looked = await api<{ found: TownThing; town: TownMap }>(`/story/town/lots/${encodeURIComponent(id)}/look`, {})
      client.setQueryData(key, { town: looked.town })
      setPicked({ thing: looked.found, at: middle(polygon) })
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'That building could not be looked at.') }
  }
  const find = (id: string) => {
    const found = places.find((place) => place.thing.id === id)
    setPicked(found ? { thing: found.thing, at: found.at } : null)
    if (found && zoom === 1) setZoom(2)
  }
  return (
    <details className="story-people story-town" open={open}>
      <summary>{map.name}</summary>
      <div className="town-zoom" role="group" aria-label="Zoom">
        {ZOOMS.map((level, index) => <button key={level} type="button" className="text-button" aria-pressed={zoom === index + 1}
          onClick={() => setZoom(index + 1)}>{level === 1 ? 'Whole town' : `×${level}`}</button>)}
      </div>
      <TownSvg map={map} zoom={zoom} picked={picked} onPick={setPicked} onLook={(id, polygon) => void look(id, polygon)} />
      {error && <p className="subtle" role="alert">{error}</p>}
      <PickedPanel picked={picked} here={map.here.place} onLine={onLine} onGo={onGo} />
      <label className="town-find">
        <span className="visually-hidden">Find a place</span>
        <select value={picked?.thing.id ?? ''} onChange={(event) => find(event.target.value)}>
          <option value="">Find a place…</option>
          {places.map(({ thing }) => <option key={thing.id} value={thing.id}>{thing.name}</option>)}
        </select>
      </label>
    </details>
  )
}

/** The building or place picked on the map: what it is, and a way to go there. */
function PickedPanel({ picked, here, onLine, onGo }: { picked: Picked | null; here: string; onLine?: (text: string) => void; onGo?: (thing: TownThing) => void }) {
  if (!picked) return <p className="subtle">Pick a building to see what is there.</p>
  const { thing } = picked
  return (
    <div className="town-picked">
      <p><strong>{thing.name}</strong> <span className="subtle">{kindName(thing)}</span>
        {thing.summary && <><br /><span className="subtle">{thing.summary}</span></>}</p>
      {thing.id !== here && (onGo || onLine) &&
        <button type="button" className="text-button" onClick={() => onGo ? onGo(thing) : onLine?.(`I head to ${thing.name}.`)}>Go there</button>}
    </div>
  )
}

interface SvgProps { map: TownMap; zoom: number; picked: Picked | null; onPick: (picked: Picked | null) => void; onLook: (id: string, polygon: Point[]) => void }

function TownSvg({ map, zoom, picked, onPick, onLook }: SvgProps) {
  const here = whereOnMap(map)
  const [left, top, span] = viewBox(map, ZOOMS[zoom - 1] ?? 1, picked?.at ?? here)
  const pick = (thing: TownThing | null, polygon: Point[]) => onPick(thing ? { thing, at: middle(polygon) } : null)
  return (
    <svg className={`town-map town-${map.style}`} viewBox={`${left.toFixed(1)} ${top.toFixed(1)} ${span.toFixed(1)} ${span.toFixed(1)}`}
      role="img" aria-label={`Map of ${map.name}.`} style={{ ['--town-scale' as string]: span / (map.size * 1.5) }}>
      <rect className="town-ground" x={-map.size * 1.2} y={-map.size * 1.2} width={map.size * 2.4} height={map.size * 2.4} />
      {map.patches.map((patch) => <polygon key={patch.id} className={`town-patch patch-${patch.kind}`} points={points(patch.polygon)}
        onClick={() => patch.hidden ? onLook(`open-${patch.id}`, patch.polygon) : pick(patch.place, patch.polygon)}>
        {patch.place ? <title>{patch.place.name}</title> : patch.hidden && <title>Open ground: look around</title>}</polygon>)}
      {map.water.map((water) => <polyline key={water.name} className="town-river" points={points(water.points)} strokeWidth={water.width}>
        <title>{water.name}</title></polyline>)}
      {map.walls && <g className="town-wall">{map.border.map(([a, b]) => <line key={`${a}-${b}`} x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} />)}</g>}
      {map.roads.map((road, index) => <polyline key={index} className="town-road" points={points(road)} />)}
      {map.lots.map((lot) => {
        const thing = lot.place ?? lot.found
        return <polygon key={lot.id} points={points(lot.polygon)} className={lotClass(lot, map, picked?.thing.id)}
          onClick={() => thing ? pick(thing, lot.polygon) : onLook(lot.id, lot.polygon)}><title>{thing?.name ?? 'A building: look at it'}</title></polygon>
      })}
      {map.districts.map((district) => <text key={district.id} className="town-district" x={district.label[0]} y={district.label[1]}
        textAnchor="middle">{district.name}</text>)}
      {zoom > 1 && namedPlaces(map).map(({ thing, at }) => <text key={thing.id} className="town-label" x={at[0]} y={at[1] - 2.5}
        textAnchor="middle">{thing.name}</text>)}
      {map.exits.map((exit) => exit.at && <text key={exit.id} className="town-exit" x={exit.at[0]} y={exit.at[1]}
        textAnchor="middle">to {exit.name}</text>)}
      <circle className="town-here" cx={here[0]} cy={here[1]} r={1.6 + 4 / (ZOOMS[zoom - 1] ?? 1)}><title>You are here</title></circle>
    </svg>
  )
}
