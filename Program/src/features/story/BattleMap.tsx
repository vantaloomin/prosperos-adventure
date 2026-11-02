import type { BattleGrid } from '../../types'
import { mapMarks } from './battleMarks'

const CELL = 18

/** The 5E fight on a grid of five-foot squares (dungeon/battlemap.py): you in the middle, foes numbered as listed. */
export function BattleMap({ grid }: { grid: BattleGrid }) {
  const { marks, minX, minY, width, height } = mapMarks(grid)
  return (
    <details className="story-battle-map">
      <summary>Battle map · {grid.square_feet} ft squares</summary>
      <svg viewBox={`0 0 ${width * CELL} ${height * CELL}`} role="img" aria-label="Battle map">
        {Array.from({ length: width * height }, (_, cell) => (
          <rect key={cell} className="square" x={(cell % width) * CELL} y={Math.floor(cell / width) * CELL} width={CELL} height={CELL} />
        ))}
        {marks.map((mark, index) => (
          <g key={index} className={`mark ${mark.kind}${mark.down ? ' down' : ''}`} transform={`translate(${(mark.x - minX + 0.5) * CELL} ${(mark.y - minY + 0.5) * CELL})`}>
            <title>{mark.title}</title>
            <circle r={CELL * 0.42} />
            <text dy="0.35em" textAnchor="middle">{mark.kind === 'you' ? '★' : mark.label}</text>
          </g>
        ))}
      </svg>
      <ol className="story-battle-legend">
        {grid.foes.map((foe, index) => <li key={`${foe.name}-${index}`}>{index + 1}. {foe.name}, {foe.feet} ft{foe.down ? ', down' : ''}</li>)}
      </ol>
    </details>
  )
}
