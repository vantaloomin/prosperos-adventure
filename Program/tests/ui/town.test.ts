import assert from 'node:assert/strict'
import { test } from 'node:test'
import { lotClass, namedPlaces, viewBox, whereOnMap, type TownMap } from '../../src/features/story/town.ts'

function town(): TownMap {
  const square: [number, number][] = [[-5, -5], [5, -5], [5, 5], [-5, 5]]
  return {
    town: 'kingswood', name: 'Kingswood', style: 'ink', walls: false, size: 160,
    patches: [{ id: 0, kind: 'square', neighborhood: 'the-crossroads', polygon: square, place: { id: 'the-green', name: 'the Green', kind: 'square' } }],
    streets: [], roads: [], water: [], border: [], square: 0,
    lots: [
      { id: '1a', neighborhood: 'mill-row', front: true, place: { id: 'varro-mill', name: "Varro's Mill", kind: 'employer', what: 'employer' }, polygon: [[100, 100], [110, 100], [110, 110]] },
      { id: '1b', neighborhood: 'mill-row', front: false, place: null, polygon: [[0, 20], [4, 20], [4, 24]] },
    ],
    districts: [{ id: 'mill-row', name: 'Mill Row', label: [30, 40], patches: [1] }],
    exits: [], here: { place: 'the-green', neighborhood: 'the-crossroads' },
  }
}

test('you are at your place on the map, else your neighborhood, else the square', () => {
  assert.deepEqual(whereOnMap(town()), [0, 0])
  assert.deepEqual(whereOnMap({ ...town(), here: { place: 'nowhere', neighborhood: 'mill-row' } }), [30, 40])
  assert.deepEqual(whereOnMap({ ...town(), here: { place: 'nowhere', neighborhood: null } }), [0, 0])
})

test('zoomed in, the view centres on a point but never runs off the map', () => {
  assert.deepEqual(viewBox(town(), 1, [50, 50]), [-120, -120, 240, 240])
  const [left, top, span] = viewBox(town(), 4, [0, 0])
  assert.deepEqual([left, top, span], [-30, -30, 60])
  const [edgeLeft] = viewBox(town(), 4, [1000, 0])
  assert.equal(edgeLeft + span, 120)
})

test('the named places are listed by name, open ground and lots alike; blank lots are not', () => {
  assert.deepEqual(namedPlaces(town()).map(({ thing }) => thing.id), ['the-green', 'varro-mill'])
  assert.equal(lotClass(town().lots[0], town(), 'varro-mill'), 'town-lot named picked')
  assert.equal(lotClass(town().lots[1], town()), 'town-lot')
  const looked = town()
  looked.lots[1].found = { id: 'lot-1b', name: "Hesk's bakery", kind: 'shop', summary: 'Bread at dawn.' }
  looked.here = { place: 'lot-1b', neighborhood: 'mill-row' }
  assert.equal(lotClass(looked.lots[1], looked), 'town-lot found here')
  assert.deepEqual(whereOnMap(looked), [8 / 3, 64 / 3])
  assert.deepEqual(namedPlaces(looked).map(({ thing }) => thing.id), ['lot-1b', 'the-green', 'varro-mill'])
})
