import assert from 'node:assert/strict'
import { test } from 'node:test'
import { freshIdeas, withIdea } from '../../src/features/story/ideas.ts'

test('a picked idea fills an empty composer, or follows what is written, and sends nothing', () => {
  assert.equal(withIdea('', 'I ask Hollis about the cart.'), 'I ask Hollis about the cart.')
  assert.equal(withIdea('  ', 'I wait.'), 'I wait.')
  assert.equal(withIdea('I sit down.', 'I wait.'), 'I sit down. I wait.')
})

test('ideas made for an earlier turn are dropped once the story moves on', () => {
  const found = { ideas: ['I wait.', 'I leave.'], turn: 4 }
  assert.deepEqual(freshIdeas(found, 4), ['I wait.', 'I leave.'])
  assert.deepEqual(freshIdeas(found, 6), [])
  assert.deepEqual(freshIdeas(null, 4), [])
})
