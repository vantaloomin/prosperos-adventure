import assert from 'node:assert/strict'
import { test } from 'node:test'
import { cardOf, knownAbout, linkText, namesIn } from '../../src/features/story/entity.ts'
import type { Gear, JournalEntry, Story, StoryPerson } from '../../src/types.ts'

const person = (key: string, name: string, place: string | null): StoryPerson => ({
  key, name, role: 'innkeeper', city: 'Kingswood', meetings: 2, last_met_at: '', notes: ['Wary of you.'], doing: 'pouring', feelings: '',
  place: place ? { id: place, name: place, city_id: 'kingswood' } : null,
})

const story = {
  scene: { city: { id: 'kingswood', name: 'Kingswood', era: '' }, place: { id: 'felled-oak', name: 'the Felled Oak', kind: 'leisure', neighborhood: '' }, local_time: '', weather: '', places: [], around: [] },
  messages: [], people: [person('agnes', 'Agnes Brill', 'felled-oak'), person('edda', 'Edda Ross', 'the-mill'), person('eddie', 'Eddie', null)],
  ready: true, dice_shown: false, branches: [], fight: { condition: 'unhurt', dead: false, fight: null }, intensity: {} as Story['intensity'],
  injury_persistence: 'permanent', factions: [{ id: 'guild', name: 'the Guild', summary: 'Buys timber.', standing: 'neutral' }],
  map: { places: [{ id: 'kingswood', name: 'Kingswood', x: 0, y: 0, visited: true, here: true }, { id: 'eriane', name: 'Eriane', x: 1, y: 1, visited: false, here: false }],
    roads: [{ from: 'kingswood', to: 'eriane', hours: 9, danger: 'medium' as const, terrain: 'forest road' }] },
} satisfies Story

const entry = (subject: string, text: string, truth: JournalEntry['truth'] = 'both'): JournalEntry => ({ id: text, kind: 'fact', subject, text, truth, source: 'narrator', created_at: '' })

test('a card knows what the character knows, never hidden truth', () => {
  const entries = [entry('Agnes Brill', 'She runs the Felled Oak.'), entry('agnes brill', 'She owes the Guild.', 'world'), entry('Edda Ross', 'Works the mill.')]
  assert.deepEqual(knownAbout(entries, ['Agnes Brill']), ['She runs the Felled Oak.'])
})

test('a person here is talked to, one elsewhere is gone to', () => {
  const here = cardOf({ kind: 'person', key: 'agnes' }, story, undefined, [])!
  assert.equal(here.title, 'Agnes Brill')
  assert.deepEqual(here.actions.map((action) => action.line ?? action.find), ['I turn to Agnes Brill.', 'I ask around about Agnes Brill.'])
  assert.deepEqual(cardOf({ kind: 'person', key: 'edda' }, story, undefined, [])!.actions[0], { label: 'Go to Edda', find: 'edda' })
  assert.equal(cardOf({ kind: 'person', key: 'nobody' }, story, undefined, []), null)
})

test('a place card names its roads and sets out', () => {
  const card = cardOf({ kind: 'place', id: 'eriane' }, story, undefined, [])!
  assert.deepEqual(card.about, ['To Kingswood: 9 hours on foot, forest road, some danger'])
  assert.deepEqual(card.actions, [{ label: 'Set out for it', line: 'I set out for Eriane.' }])
  assert.deepEqual(cardOf({ kind: 'place', id: 'kingswood' }, story, undefined, [])!.actions, [])
})

test('an item card proposes lines, and selling only where a shop buys it', () => {
  const gear: Gear = { coins: 0, currency: { code: 'cr' }, slots: { used: 1, max: 10 }, items: [{ id: 'i1', item_id: 'bread', name: 'Loaf of black bread', category: 'food', qty: 2, slots: 1 }], shop: null }
  assert.deepEqual(cardOf({ kind: 'item', id: 'i1' }, story, gear, [])!.actions.map((action) => action.line), ['I use my loaf of black bread.', 'I look over my loaf of black bread.'])
  const selling = { ...gear, shop: { place_id: 'p', open: true, keeper: 'Agnes', haggled: 0, stock: [], offers: { i1: 10 } } }
  assert.equal(cardOf({ kind: 'item', id: 'i1' }, story, selling, [])!.actions.length, 3)
})

test('the prose links whole names, and a first name only when no one shares it', () => {
  const names = namesIn(story).map((link) => link.name)
  assert.deepEqual(names, ['Agnes Brill', 'Edda Ross', 'the Guild', 'Eddie', 'Agnes', 'Edda'])
  const parts = linkText('Agnes Brill nods. Agnesine waits; Edda and the Guild watch.', namesIn(story))
  assert.deepEqual(parts.map((part) => typeof part === 'string' ? part : `[${part.name}]`), ['[Agnes Brill]', ' nods. Agnesine waits; ', '[Edda]', ' and ', '[the Guild]', ' watch.'])
})
