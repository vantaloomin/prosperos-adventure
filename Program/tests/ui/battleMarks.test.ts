import assert from 'node:assert/strict'
import { test } from 'node:test'
import { mapMarks } from '../../src/features/story/battleMarks.ts'

test('the battle map frames everyone with a square to spare and numbers the foes', () => {
  const { marks, minX, minY, width, height } = mapMarks({
    square_feet: 5, area: null,
    foes: [{ name: 'the bandit', x: 0, y: -1, feet: 5, down: false }, { name: 'the archer', x: 9, y: -9, feet: 45, down: true }],
    allies: [{ name: 'Corin', x: 0, y: 1, down: false }],
  })
  assert.deepEqual([minX, minY, width, height], [-1, -10, 12, 13])
  assert.deepEqual(marks.map((mark) => [mark.kind, mark.label]), [['you', 'You'], ['foe', '1'], ['foe', '2'], ['ally', 'C']])
  assert.equal(marks[2].title, 'the archer, 45 ft, down')
})
