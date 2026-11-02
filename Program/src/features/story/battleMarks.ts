import type { BattleGrid } from '../../types'

/** One mark on the battle map: the character, a foe (numbered as the legend numbers it) or a companion. */
export interface MapMark { x: number; y: number; label: string; kind: 'you' | 'foe' | 'ally'; down: boolean; title: string }

/** The marks to draw and the squares around them (a square of margin on every side), for dungeon/battlemap.py's map. */
export function mapMarks(grid: BattleGrid): { marks: MapMark[]; minX: number; minY: number; width: number; height: number } {
  const marks: MapMark[] = [
    { x: 0, y: 0, label: 'You', kind: 'you', down: false, title: 'You' },
    ...grid.foes.map((foe, index): MapMark => ({ x: foe.x, y: foe.y, label: String(index + 1), kind: 'foe', down: foe.down, title: `${foe.name}, ${foe.feet} ft${foe.down ? ', down' : ''}` })),
    ...grid.allies.map((ally): MapMark => ({ x: ally.x, y: ally.y, label: ally.name.slice(0, 1).toUpperCase(), kind: 'ally', down: ally.down, title: `${ally.name}${ally.down ? ', down' : ''}` })),
  ]
  const xs = marks.map((mark) => mark.x)
  const ys = marks.map((mark) => mark.y)
  const minX = Math.min(...xs) - 1
  const minY = Math.min(...ys) - 1
  return { marks, minX, minY, width: Math.max(...xs) + 2 - minX, height: Math.max(...ys) + 2 - minY }
}
