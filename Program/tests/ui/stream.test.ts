import assert from 'node:assert/strict'
import { test } from 'node:test'
import { ndjsonLines } from '../../src/ndjson.ts'

test('ndjsonLines keeps an unfinished line for the next piece of the stream', () => {
  const [first, rest] = ndjsonLines('{"text":"The bouncer "}\n{"text":"swi')
  assert.deepEqual(first, [{ text: 'The bouncer ' }])
  const [second, left] = ndjsonLines(`${rest}ngs."}\n{"done":{"reply":null}}\n`)
  assert.deepEqual(second, [{ text: 'swings.' }, { done: { reply: null } }])
  assert.equal(left, '')
})
