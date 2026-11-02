import assert from 'node:assert/strict'
import { test } from 'node:test'
import { NOTE_SWITCH, noteKey, noteLook } from '../../src/features/story/noteState.ts'
test("the author's note button is quiet when empty, lit when on, outlined when written but switched off", () => {
  assert.equal(noteLook('', true), 'off')
  assert.equal(noteLook('   ', false), 'off')
  assert.equal(noteLook('Keep it light.', true), 'on')
  assert.equal(noteLook('Keep it light.', false), 'paused')
  assert.deepEqual(noteKey('story'), ['authors-note', 'story'])
})

test("the note's switch is labeled by what it does, so it reads clearly on and off", () => {
  assert.equal(NOTE_SWITCH, 'Use this note')
  assert.ok(!/^(on|off)$/i.test(NOTE_SWITCH))
})
