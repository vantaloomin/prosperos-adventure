import assert from 'node:assert/strict'
import { test } from 'node:test'
import { categoryOf, citiesOfWorld, CUSTOM_WORLD, homeWorlds, cityFacts, definitionOf, exportName, groupNotes, matchesCity, parseDefinition, shelveCities, slugify, type CityListing } from '../../src/features/world/cityText.ts'

const city = (extra: Partial<CityListing> = {}): CityListing => ({
  id: 'baltimore', name: 'Baltimore', region: 'Maryland', country: 'US', setting: 'real', era: 'modern', summary: '', basis: '',
  counts: { neighborhoods: 21, places: 124, colleges: 9, employers: 16, annual_events: 12 }, builtin: true, origin: 'builtin',
  distribution: 'public', ...extra,
})

test('slugs are lowercase ascii ids', () => {
  assert.equal(slugify('My Ellerbrück!'), 'my-ellerbruck')
  assert.equal(slugify('  --New   York-- '), 'new-york')
  assert.equal(slugify('!!!'), '')
})

test('derived keys are dropped from an exported definition', () => {
  assert.deepEqual(definitionOf({ id: 'x', data_version: 'abc', revision: 2, origin: 'user', builtin: false, name: 'X' }), { id: 'x', name: 'X' })
  assert.equal(exportName('my-city'), 'my-city.json')
})

test('the editor text must be a JSON object', () => {
  assert.deepEqual(parseDefinition('{"id": "a"}'), { ok: true, value: { id: 'a' } })
  assert.equal(parseDefinition('[1]').ok, false)
  const broken = parseDefinition('{"id": ')
  assert.equal(broken.ok, false)
  assert.match(broken.ok ? '' : broken.error, /not valid JSON/)
})

test('cities shelve as Real / Modern, Other Eras, Fictional and Custom, each sorted by name', () => {
  const shelves = shelveCities([
    city({ id: 'z', name: 'Zed', origin: 'user', category: 'custom' }), city({ category: 'real' }),
    city({ id: 'oz', name: 'The Emerald City', category: 'fictional' }), city({ id: 'a', name: 'Arden', origin: 'user', category: 'custom' }),
    city({ id: 'old', name: 'Old Server City' }),
  ])
  assert.deepEqual(shelves.map((shelf) => [shelf.title, shelf.cities.map((item) => item.name)]), [
    ['Real / Modern', ['Baltimore', 'Old Server City']], ['Other Eras', []], ['Fictional', ['The Emerald City']], ['Custom', ['Arden', 'Zed']],
  ])
  assert.equal(categoryOf({ name: 'x', category: 'something-else' }), 'real')
})

test("the Worlds page lists the open world's cities, or the cities on their own, with every pack and custom city", () => {
  const cities = [
    city({ id: 'kingswood', world: 'vallarith' }), city({ id: 'hollin', world: 'babel' }), city({ id: 'haddon-harbor', world: null }),
    city({ id: 'old', world: undefined }), city({ id: 'mine', origin: 'user' }), city({ id: 'dropped', origin: 'pack', world: null }),
  ]
  const ids = (home: string) => citiesOfWorld(cities, home).map((item) => item.id)
  assert.deepEqual(ids('kingswood'), ['kingswood', 'mine', 'dropped'])
  assert.deepEqual(ids('haddon-harbor'), ['haddon-harbor', 'old', 'mine', 'dropped'])
  assert.deepEqual(ids('mine'), ['haddon-harbor', 'old', 'mine', 'dropped'])
})

test('the city search matches name, other names, region and country, ignoring accents and case', () => {
  const ellerbruck = city({ name: 'Ellerbrück', region: 'Hesse', country: 'a small German principality', aliases: ['the market town'] })
  assert.ok(matchesCity(ellerbruck, 'ellerbruck'))
  assert.ok(matchesCity(ellerbruck, ' HESSE '))
  assert.ok(matchesCity(ellerbruck, 'german'))
  assert.ok(matchesCity(ellerbruck, 'market'))
  assert.ok(matchesCity(ellerbruck, ''))
  assert.ok(!matchesCity(ellerbruck, 'gotham'))
})

test('facts read naturally', () => {
  assert.equal(cityFacts(city()), 'Real city · modern · 21 neighborhoods, 124 places')
  assert.equal(cityFacts(city({ setting: 'original', counts: { ...city().counts, neighborhoods: 1, places: 1 } })), 'Original setting · modern · 1 neighborhood, 1 place')
})


test('notes that say the same about several places become one line', () => {
  const many = Array.from({ length: 8 }, (_, index) => `Mill ${index + 1}: filled in cost as '$'.`)
  assert.deepEqual(groupNotes(['Timezone set to UTC.', 'Bluebird Diner: filled in cost as \'$\'.', 'Oak Hall: ignored the field "x", which the app does not use.', 'Pier: filled in cost as \'$\'.']),
    ['Timezone set to UTC.', "Bluebird Diner and Pier: filled in cost as '$'.", 'Oak Hall: ignored the field "x", which the app does not use.'])
  assert.deepEqual(groupNotes(many), ["Mill 1, Mill 2, Mill 3, Mill 4, Mill 5 and 3 more: filled in cost as '$'."])
})

test('where someone lives is picked world first: featured worlds in order, Custom last, never a road', () => {
  const cities = [
    city({ id: 'hollin', name: 'Hollin', world: 'vallarith', world_name: 'Vallarith' }),
    city({ id: 'kingswood', name: 'Kingswood', world: 'vallarith', world_name: 'Vallarith' }),
    city({ id: 'vallarith-road', name: 'the Road', world: 'vallarith', world_name: 'Vallarith', home: false }),
    city({ id: 'haven', name: 'Haven', world: 'havenbrooke', world_name: 'Havenbrooke' }),
    city({ id: 'mine', name: 'Mine', origin: 'user', world: null }),
    city({ id: 'the-concourse', name: 'the Concourse', world: 'babel', world_name: 'BABEL' }),
  ]
  const worlds = homeWorlds(cities, [{ id: 'kingswood' }, { id: 'haven' }, { id: 'the-concourse' }])
  assert.deepEqual(worlds.map((world) => world.name), ['Vallarith', 'Havenbrooke', 'BABEL', 'Custom'])
  assert.deepEqual(worlds[0].towns.map((town) => town.id), ['hollin', 'kingswood'])
  assert.equal(worlds[3].id, CUSTOM_WORLD)
})
