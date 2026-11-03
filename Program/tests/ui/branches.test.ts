import assert from 'node:assert/strict'
import { test } from 'node:test'
import { branchName } from '../../src/features/story/storyText.ts'

test('a branch is called by its name, else by the character it asked again, else nothing', () => {
  assert.equal(branchName({ label: 'The merchants', reask: { seat: 'hesk', name: 'Hesk' } }), 'The merchants')
  assert.equal(branchName({ label: '', reask: { seat: 'hesk', name: 'Hesk' } }), 'What if Hesk had chosen otherwise?')
  assert.equal(branchName({ label: '', reask: null }), '')
})
