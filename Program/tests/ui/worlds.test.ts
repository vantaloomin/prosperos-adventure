import { test } from 'node:test'
import assert from 'node:assert/strict'
import { homeLine, initial, personaName, personaRef, personaTitle, whereLine } from '../../src/features/worlds/worldsText.ts'

test('a persona without a name is never called You', () => {
  assert.equal(personaName({ name: '  ' }), '')
  assert.equal(personaTitle({ name: '' }), 'Your first persona')
  assert.equal(personaRef({ name: '' }), 'this persona')
  assert.equal(personaRef({ name: 'Sam' }), 'Sam')
  assert.equal(initial({ name: 'sam' }), 'S')
  assert.equal(initial({ name: '' }), '')
  assert.equal(whereLine({ name: 'Sam' }, { name: 'Baltimore' }), 'Sam · Baltimore')
  assert.equal(whereLine({ name: '' }, { name: 'Baltimore' }), 'Baltimore')
})

test('a world says where the persona lives', () => {
  const home = { city_id: 'haddon-harbor', city: 'Haddon Harbor', region: 'Maine', neighbourhood: 'ridge-road', neighbourhood_name: 'Ridge Road', set_by: 'app' as const }
  assert.equal(homeLine({ home: null }), 'No home yet')
  assert.equal(homeLine({ home }), 'Ridge Road, Haddon Harbor')
  assert.equal(homeLine({ home: { ...home, neighbourhood_name: '' } }), 'Haddon Harbor')
})
