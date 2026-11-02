import type { StoryInterior as Interior } from '../../types'

const SIZE = 300
const PAD = 26
const BOX = { w: 70, h: 22 }

type Room = Interior['rooms'][number]

/** Where each seen room sits: where the interior's author drew it, else in a row for its level, in the order seen. */
function layout(interior: Interior): Map<string, { x: number; y: number }> {
  const rows = [...interior.levels.map((level) => level.id), null]
  const used = rows.map(() => 0)
  const found = new Map<string, { x: number; y: number }>()
  for (const room of interior.rooms) {
    if (room.map) {
      found.set(room.id, { x: PAD + room.map.x * (SIZE - 2 * PAD), y: PAD + room.map.y * (SIZE - 2 * PAD) })
      continue
    }
    const row = Math.max(0, rows.indexOf(room.level))
    found.set(room.id, { x: PAD + 20 + used[row] * (BOX.w + 14), y: PAD + row * ((SIZE - 2 * PAD) / Math.max(1, rows.length - 1)) })
    used[row] += 1
  }
  return found
}

/** The interior your character is inside (dungeon/delving.py), as far as they know it: the rooms they have been in,
 *  the passages between them, and where they are. Ways they have seen but not taken show as short stubs. */
export function StoryInterior({ interior, open, onLine }: { interior: Interior | null | undefined; open?: boolean; onLine?: (text: string) => void }) {
  if (!interior) return null
  const at = layout(interior)
  const here = interior.rooms.find((room) => room.here)
  const known = interior.passages.filter((passage) => passage.to_known)
  const unknown = interior.passages.filter((passage) => !passage.to_known)
  const levelOf = (room: Room) => interior.levels.find((level) => level.id === room.level)?.name
  return (
    <details className="story-people story-map story-interior" open={open}>
      <summary>{interior.name}{here ? ` (${here.name})` : ''}</summary>
      <svg viewBox={`0 0 ${SIZE} ${SIZE}`} role="img" aria-label={`Rooms of ${interior.name} you know`}>
        {known.map((passage) => {
          const a = at.get(passage.between[0]), b = at.get(passage.between[1])
          return a && b ? <line key={passage.between.join('-')} className={`interior-way way-${passage.kind}`} x1={a.x} y1={a.y} x2={b.x} y2={b.y} /> : null
        })}
        {unknown.map((passage, index) => {
          const from = passage.between.find((id) => at.has(id))
          const a = from ? at.get(from) : undefined
          if (!a) return null
          const angle = (index * 2.4) % (Math.PI * 2)
          return <line key={`stub-${passage.between.join('-')}`} className={`interior-way stub way-${passage.kind}`} x1={a.x} y1={a.y}
            x2={a.x + Math.cos(angle) * 42} y2={a.y + Math.sin(angle) * 32} />
        })}
        {interior.rooms.map((room) => {
          const p = at.get(room.id)
          if (!p) return null
          return (
            <g key={room.id} className={`interior-room${room.here ? ' here' : ''}`} transform={`translate(${p.x} ${p.y})`}>
              <rect x={-BOX.w / 2} y={-BOX.h / 2} width={BOX.w} height={BOX.h} rx={3} />
              <text y={3.5} textAnchor="middle">{room.name.length > 15 ? `${room.name.slice(0, 14)}…` : room.name}</text>
              <title>{room.name}{levelOf(room) ? `, ${levelOf(room)}` : ''}{room.here ? ' (you are here)' : ''}</title>
            </g>
          )
        })}
      </svg>
      <ul className="map-places">
        {interior.rooms.filter((room) => !room.here).map((room) => <li key={room.id}>
          <span>{room.name}{levelOf(room) ? <span className="subtle"> · {levelOf(room)}</span> : null}</span>
          {onLine && <button type="button" className="text-button" onClick={() => onLine(`I go back to ${room.name.toLowerCase()}.`)}>Go back</button>}
        </li>)}
      </ul>
    </details>
  )
}
