import assert from 'node:assert/strict'
import { test } from 'node:test'
import { arrivalText } from '../../src/features/worlds/arrival.ts'

test('a page that followed a switch says where it went, or that it came along', () => {
  assert.equal(arrivalText('Kingswood'), 'Now in Kingswood. You switched worlds on another screen, so this one came too.')
  assert.equal(arrivalText(null), 'Now in the world you opened on another screen. This one came too.')
})
