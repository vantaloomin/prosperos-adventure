import assert from 'node:assert/strict'
import { test } from 'node:test'
import { nextTile, rowEdges } from '../../src/features/story/titleText.ts'

test('the world row shows more only on a side that has more', () => {
  assert.deepEqual(rowEdges(0, 800, 800), { before: false, after: false })
  assert.deepEqual(rowEdges(0, 800, 1400), { before: false, after: true })
  assert.deepEqual(rowEdges(300, 800, 1400), { before: true, after: true })
  assert.deepEqual(rowEdges(598, 800, 1400), { before: true, after: false })
})

test('arrow keys move along the world row and stop at its ends', () => {
  assert.equal(nextTile(0, 'ArrowLeft', 4), 0)
  assert.equal(nextTile(0, 'ArrowRight', 4), 1)
  assert.equal(nextTile(3, 'ArrowRight', 4), 3)
  assert.equal(nextTile(2, 'Home', 4), 0)
  assert.equal(nextTile(0, 'End', 4), 3)
  assert.equal(nextTile(1, 'a', 4), 1)
})
