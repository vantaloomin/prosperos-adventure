import type { DieFace } from './storyText'
import type { Tumble } from './dice'

// The outline of each die by its sides, on a 40 by 40 box.
const SHAPES: Record<number, string> = {
  4: '20,3 37,35 3,35', 6: '6,6 34,6 34,34 6,34', 8: '20,2 38,20 20,38 2,20', 10: '20,2 37,15 20,38 3,15',
  12: '20,2 38,15 31,37 9,37 2,15',
}

function caption(face: DieFace): string {
  if (face.key === 'action') return 'action'
  if (face.key.startsWith('fate')) return 'fate'
  if (face.key === 'challenge1' || face.key === 'challenge2') return 'challenge'
  return face.key === 'stat' ? `d${face.sides}` : face.key === 'tens' ? 'd100' : ''
}

/** The dice in a roll card: the percentile pair and the stat die. A click lands them at once. */
export function DiceTray({ tumble }: { tumble: Tumble }) {
  const { faces, shown, landed, done, skip } = tumble
  const spoken = faces.map((face) => (face.key === 'stat' ? `${face.value} on the d${face.sides}` : face.value)).join(', ')
  return (
    <button type="button" className="dice-tray" onClick={skip} disabled={done} aria-label={done ? `Dice: ${spoken}` : 'Dice rolling. Land them now'}>
      {faces.map((face, index) => (
        <span key={face.key} className={landed[index] ? 'die landed' : 'die tumbling'} data-die={face.key}>
          <svg viewBox="0 0 40 40" aria-hidden="true">
            <polygon points={SHAPES[face.sides] ?? SHAPES[10]} />
            <text x="20" y={face.sides === 4 ? 29 : 24} textAnchor="middle">{shown[index]}</text>
          </svg>
          <small aria-hidden="true">{caption(face)}</small>
        </span>
      ))}
    </button>
  )
}
