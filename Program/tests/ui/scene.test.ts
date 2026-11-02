import assert from 'node:assert/strict'
import { test } from 'node:test'
import { hasWidget, partyOf, peopleHere, sceneWidgets } from '../../src/features/story/scene.ts'
import type { Story, StoryPerson } from '../../src/types.ts'

const person = (key: string, place: string | null): StoryPerson => ({
  key, name: key, role: 'innkeeper', city: 'Kingswood', meetings: 1, last_met_at: '', notes: [], doing: '', feelings: '',
  place: place ? { id: place, name: place, city_id: 'kingswood' } : null,
})

function story(changes: Partial<Story> = {}, city = 'kingswood'): Story {
  return {
    scene: { city: { id: city, name: 'Kingswood', era: '' }, place: { id: 'felled-oak', name: 'the Felled Oak', kind: 'leisure', neighborhood: '' }, local_time: '', weather: '', places: [], around: [] },
    messages: [{ id: 'm1', seq: 1, role: 'user', text: 'I look around.', reply_to: null, status: 'complete', error: null, city_id: city, place_id: 'felled-oak', created_at: '' }],
    people: [], ready: true, dice_shown: false, branches: [], fight: { condition: 'unhurt', dead: false, fight: null },
    intensity: {} as Story['intensity'], map: { places: [], roads: [] }, injury_persistence: 'permanent', ...changes,
  }
}

const fight: Story['fight'] = { condition: 'hurt', dead: false, fight: { round: 2, foes: [{ name: 'a big man', state: 'wounded', wound: null }] } }

test('with nothing going on, the scene panel shows the journal', () => {
  assert.deepEqual(sceneWidgets(story(), false), ['journal'])
})

test('the scene picks at most two widgets, the fight first', () => {
  const people = [person('Agnes Brill', 'felled-oak'), person('Edda', 'the-mill')]
  assert.deepEqual(sceneWidgets(story({ people }), false), ['here'])
  assert.deepEqual(sceneWidgets(story({ people }), true), ['pack', 'here'])
  assert.deepEqual(sceneWidgets(story({ people, fight }), true), ['fight', 'pack'])
  assert.deepEqual(sceneWidgets(story({}, 'vallarith-road'), false), ['map'])
})

test('the people here are the ones met at this very place', () => {
  const people = [person('Agnes Brill', 'felled-oak'), person('Edda', 'the-mill'), person('Hob', null)]
  assert.deepEqual(peopleHere(story({ people })).map((one) => one.key), ['Agnes Brill'])
})

test('the party is here wherever the story is, and has its own widget', () => {
  const people = [person('Agnes Brill', 'felled-oak'), { ...person('Hesk', null), party: true }]
  assert.deepEqual(peopleHere(story({ people })).map((one) => one.key), ['Agnes Brill', 'Hesk'])
  assert.deepEqual(partyOf(story({ people })).map((one) => one.key), ['Hesk'])
  assert.equal(hasWidget(story({ people }), 'party'), true)
  assert.equal(hasWidget(story({ people: people.slice(0, 1) }), 'party'), false)
})

test('the drawer leaves out what has nothing to show', () => {
  assert.equal(hasWidget(story(), 'fight'), false)
  assert.equal(hasWidget(story({ fight }), 'fight'), true)
  assert.equal(hasWidget(story(), 'chapters'), false)
  assert.equal(hasWidget(story(), 'branches'), false)
  assert.equal(hasWidget(story({ messages: [] }), 'sheet'), false)
  assert.equal(hasWidget(story(), 'dice'), false)
  assert.equal(hasWidget(story({ dice_shown: true }), 'dice'), true)
  assert.equal(hasWidget(story(), 'rules'), true)
})

test('inside an interior the scene shows its rooms, after a fight and before the road map', () => {
  const interior: Story['interior'] = {
    id: 'abandoned-keep', name: 'The Abandoned Keep', style: 'keep', levels: [],
    rooms: [{ id: 'broken-gate', name: 'The broken gate', level: null, kind: 'gate', map: null, here: true, cleared: false }], passages: [],
  }
  assert.deepEqual(sceneWidgets(story({ interior }, 'vallarith-road'), false), ['inside', 'map'])
  assert.deepEqual(sceneWidgets(story({ interior, fight }, 'vallarith-road'), false), ['fight', 'inside'])
  assert.equal(hasWidget(story({ interior }), 'inside'), true)
  assert.equal(hasWidget(story(), 'inside'), false)
})
