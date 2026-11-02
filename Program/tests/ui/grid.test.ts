import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  addable, addTile, cleanGrid, cleanSaved, dropTile, moveTile, onGrid, removeTile, resizeTile, seedGrid, withGrid, withoutGrid, DEFAULT_NAME, MOST_TILES,
} from '../../src/features/story/grid.ts'

const order = (grid: { tiles: { widget: string }[] }) => grid.tiles.map((tile) => tile.widget)

test('a first grid is this scene, then the pins, then the drawer tabs, each once', () => {
  assert.deepEqual(order(seedGrid()), ['scene', 'sheet', 'pack', 'journal'])
  assert.deepEqual(order(seedGrid(['map', 'pack'])), ['scene', 'map', 'pack', 'sheet', 'journal'])
  assert.equal(seedGrid().tiles[0].size, 'wide')
})

test('a saved grid drops unknown widgets, repeats and sizes', () => {
  const grid = cleanGrid({ tiles: [{ widget: 'sheet', size: 'tall' }, { widget: 'sheet' }, { widget: 'phone' }, { widget: 'map', size: 'huge' }, null] })
  assert.deepEqual(grid.tiles, [{ widget: 'sheet', size: 'tall' }, { widget: 'map', size: 'small' }])
  assert.deepEqual(order(cleanGrid('nonsense')), order(seedGrid()))
  const many = { tiles: ['scene', 'fight', 'here', 'sheet', 'pack', 'journal', 'map', 'people', 'powers', 'chapters', 'branches', 'notebook', 'export', 'rules', 'art'].map((widget) => ({ widget })) }
  assert.equal(cleanGrid(many).tiles.length, MOST_TILES)
})

test('tiles move, drop, resize and come off; a tile already there is not added twice', () => {
  const grid = seedGrid()
  assert.deepEqual(order(moveTile(grid, 'journal', -1)), ['scene', 'sheet', 'journal', 'pack'])
  assert.equal(moveTile(grid, 'scene', -1), grid)
  assert.deepEqual(order(dropTile(grid, 'journal', 'scene')), ['journal', 'scene', 'sheet', 'pack'])
  assert.equal(resizeTile(grid, 'sheet', 'tall').tiles[1].size, 'tall')
  assert.deepEqual(order(removeTile(grid, 'pack')), ['scene', 'sheet', 'journal'])
  assert.equal(addTile(grid, 'sheet'), grid)
  assert.deepEqual(order(addTile(grid, 'map')), ['scene', 'sheet', 'pack', 'journal', 'map'])
  assert.deepEqual(addable(removeTile(grid, 'scene'), ['sheet', 'map']), ['scene', 'map'])
  assert.ok(onGrid(grid, 'pack'))
  assert.ok(!onGrid(grid, 'map'))
})

test('layouts are kept by name, and one always stays', () => {
  const first = cleanSaved(null, ['map'])
  assert.equal(first.current, DEFAULT_NAME)
  assert.deepEqual(order(first.layouts[DEFAULT_NAME]), ['scene', 'map', 'sheet', 'pack', 'journal'])
  const two = withGrid(first, removeTile(first.layouts[DEFAULT_NAME], 'map'), '  Fights  ')
  assert.equal(two.current, 'Fights')
  assert.deepEqual(Object.keys(two.layouts), [DEFAULT_NAME, 'Fights'])
  const back = withoutGrid(two, 'Fights')
  assert.equal(back.current, DEFAULT_NAME)
  assert.deepEqual(Object.keys(withoutGrid(back, DEFAULT_NAME).layouts), [DEFAULT_NAME])
  assert.equal(cleanSaved({ current: 'Gone', layouts: { Mine: { tiles: [] } } }).current, 'Mine')
})
