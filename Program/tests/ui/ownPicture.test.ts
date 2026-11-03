import assert from 'node:assert/strict'
import { test } from 'node:test'
import { LONGEST, shrunk } from '../../src/features/story/ownPicture.ts'

test('a picture that fits is sent at its own size, a bigger one shrinks to fit on its longer side', () => {
  assert.deepEqual(shrunk(800, 1200), { width: 800, height: 1200 })
  assert.deepEqual(shrunk(4096, 3072), { width: LONGEST, height: 1536 })
  assert.deepEqual(shrunk(1000, 5000), { width: 410, height: LONGEST })
})

test('a picture the player added says so, beside being their likeness', async () => {
  const { artNotes } = await import('../../src/features/story/artText.ts')
  assert.equal(artNotes({ own: true, reference: true }), ' · added by you · their likeness')
  assert.equal(artNotes({ own: false, reference: true }), ' · their likeness')
  assert.equal(artNotes({ reference: false }), '')
})
