import assert from 'node:assert/strict'
import { test } from 'node:test'
import { worldAction } from '../../src/features/story/titleText.ts'

test("a world card begins the story where it is, returns to the persona's own world, or goes somewhere new", () => {
  assert.equal(worldAction({ name: 'Vallarith', here: true, yours: false }), 'Begin in Vallarith')
  assert.equal(worldAction({ name: 'BABEL', here: false, yours: true }), 'Return to BABEL')
  assert.equal(worldAction({ name: 'Havenbrooke', here: false, yours: false }), 'Go to Havenbrooke')
})
