import assert from 'node:assert/strict'
import { test } from 'node:test'
import { addedFact, after, before, comparable, effect, history, proposals, title, withProposal, type Change, type Turn } from '../../src/features/assistant/proposals.ts'
import { createStore } from '../../src/features/assistant/store.ts'
import type { Journal } from '../../src/types.ts'

const feelings: Change = { kind: 'feelings', key: 'pell', name: 'Pell', before: { trust: 0, affection: 1, respect: 0, fear: 2, desire: 0 }, values: { trust: 3 } }

test('each proposal reads as what it changes, and GM edits say so', () => {
  assert.equal(title(feelings), 'How Pell feels')
  assert.equal(before(feelings), 'trust 0')
  assert.equal(after(feelings), 'trust 3')
  assert.match(effect(feelings), /^A GM edit/)
  const lore: Change = { kind: 'lore_add', title: '', text: 'It rains.', keywords: ['rain', 'storm'], always: false, visibility: 'gm' }
  assert.equal(title(lore), 'New lore')
  assert.equal(effect(lore), 'Comes in when the story says “rain” or “storm”. GM only: no character reads it.')
  assert.equal(comparable(lore), false)
  const note: Change = { kind: 'authors_note', before: '', enabled: true, text: 'Keep it quiet.' }
  assert.equal(comparable(note), false, 'nothing to compare with an empty note')
  assert.equal(comparable({ ...note, before: 'Loud.' }), true)
  assert.equal(title({ kind: 'beat_cut', beat_id: 'b', arc: 'The Eight Pieces', text: 'x', cut: false }), 'Bring back a beat in The Eight Pieces')
})

test('history sends the latest turns, cut to a readable length', () => {
  const turns: Turn[] = Array.from({ length: 7 }, (_, index) => ({ id: `t${index}`, message: `ask ${index}`, reply: index === 6 ? ' ' : 'x'.repeat(5000), proposals: [] }))
  const sent = history(turns)
  assert.equal(sent[0].content, 'ask 2')
  assert.equal(sent[1].content.length, 4000)
  assert.equal(sent[sent.length - 1].content, 'ask 6', 'an empty reply is left out')
})

test('a proposal changes in place, and a new one starts pending', () => {
  let next = 0
  const made = proposals([feelings], () => `p${next++}`)
  assert.deepEqual(made, [{ id: 'p0', change: feelings, status: 'pending' }])
  const turns = withProposal([{ id: 't', message: 'm', reply: 'r', proposals: made }], 'p0', { status: 'applied', undo: 'x' })
  assert.equal(turns[0].proposals[0].status, 'applied')
  assert.equal(turns[0].proposals[0].undo, 'x')
})

test('the store opens on a passage and closing forgets it', () => {
  const store = createStore<Turn>(false)
  let calls = 0
  store.subscribe(() => { calls += 1 })
  store.ask({ id: 'm1', text: 'Rain.' })
  assert.deepEqual(store.get().focus, { id: 'm1', text: 'Rain.' })
  assert.equal(store.get().open, true)
  store.toggle()
  assert.equal(store.get().open, false)
  assert.equal(store.get().focus, null)
  assert.ok(calls >= 3)
})

test('the journal fact a proposal added is found for Undo', () => {
  const journal = { entries: [{ id: 'k2', subject: 'Mara', text: 'Mara keeps the inn.' }, { id: 'k1', subject: 'Mara', text: 'Other.' }], quests: [] } as unknown as Journal
  assert.equal(addedFact(journal, 'Mara', 'Mara keeps the inn.'), 'k2')
  assert.equal(addedFact(journal, 'Pell', 'x'), undefined)
})
