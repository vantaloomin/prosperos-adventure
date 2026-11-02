import assert from 'node:assert/strict'
import { test } from 'node:test'
import { alliesText, backingText, neitherText, outcomeText, pullText, sortedPeople, splitShares, splitText, stageLabel, viewLabel } from '../../src/features/story/politicsText.ts'

const sides = [{ name: 'Wet', stand: 'see Prohibition repealed' }, { name: 'Dry', stand: 'keep the country dry' }]

test('the town split adds up to 100 and reads out', () => {
  assert.deepEqual(splitShares({ first: 42, second: 27, neither: 51 }), { first: 35, second: 23, neither: 42 })
  assert.deepEqual(splitShares({ first: 0, second: 0, neither: 0 }), { first: 0, second: 0, neither: 100 })
  assert.equal(splitText({ sides, split: { first: 42, second: 27, neither: 51 } }), "Around town: 35% Wet, 23% Dry, 42% don't much care.")
  assert.equal(neitherText({ first: 42, second: 27, neither: 51 }), "42% don't much care")
})

test('views, stages and pull read in words', () => {
  assert.equal(viewLabel(-1, { sides }), 'Leans: Dry')
  assert.equal(viewLabel(2, { sides }), 'Strongly: Wet')
  assert.equal(viewLabel(0, { sides }), "Doesn't much care")
  assert.equal(stageLabel({ stage: 'open', real: true }), 'Out in the open · real history')
  assert.equal(stageLabel({ stage: 'heated', real: false }), 'Heated')
  assert.equal(pullText({ pull: 4, change: 1 }), 'Strong pull, up after a win')
  assert.equal(pullText({ pull: 2, change: 0 }), 'Some pull')
})

test('factions name their allies, rivals and the side they back', () => {
  const factions = [{ id: 'hall', name: 'Tammany Hall' }, { id: 'league', name: 'The League' }, { id: 'unions', name: 'The unions' }]
  const relations = [{ a: 'hall', b: 'league', stance: -2, by: 'world' as const }, { a: 'hall', b: 'unions', stance: 1, by: 'world' as const },
    { a: 'league', b: 'unions', stance: 0, by: 'world' as const }]
  assert.equal(alliesText('hall', { factions: factions as never, relations }), 'Allies: The unions. Rivals: The League.')
  assert.equal(alliesText('unions', { factions: factions as never, relations }), 'Allies: Tammany Hall.')
  assert.deepEqual(backingText({ sides, lines: { hall: 0, league: 1, unions: 0 } }, factions), ['Backing Wet: Tammany Hall, The unions.', 'Backing Dry: The League.'])
})

test('a settled issue says how it went, and when the user picked it', () => {
  const options = [{ option: 0, label: 'The pier is built.', odds: 0.6, reasons: [] }, { option: 1, label: 'No pier.', odds: 0.3, reasons: [] }]
  assert.equal(outcomeText({ settled: { options, picked: 0, picked_by: 'dice' } }), 'The pier is built.')
  assert.equal(outcomeText({ settled: { options, picked: 1, picked_by: 'user' } }), 'No pier. You picked how it went.')
  assert.equal(outcomeText({ settled: null }), null)
})

test('people with a view come first, and five who do not much care fold away', () => {
  const person = (name: string, view: number) => ({ name, views: { p: { view } } })
  const few = sortedPeople([person('a', 0), person('b', -2), person('c', 1)], 'p')
  assert.deepEqual(few.shown.map((item) => item.name), ['b', 'c', 'a'])
  assert.equal(few.folded.length, 0)
  const many = sortedPeople([person('a', 0), person('b', 0), person('c', 1), person('d', 0), person('e', 0)], 'p')
  assert.deepEqual([many.shown.map((item) => item.name), many.folded.length], [['c'], 4])
})
