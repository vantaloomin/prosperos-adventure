import assert from 'node:assert/strict'
import { test } from 'node:test'
import { LongStringDropper, isWorldMap, readWorldMap } from '../../src/features/world/worldMap.ts'

const map = {
  format: 'marinara-hierarchical-map', name: 'Harbour "Light"\\3',
  definition: { locations: [{ id: 'a', parentId: null, name: 'Port \\"Ellery\\"' }] },
  artwork: [{ filename: 'a.png', data: `data:image/png;base64,${'A'.repeat(500)}` }],
}

/** The text through the dropper in pieces of `size`, so strings and escapes are split across chunks. */
function inPieces(text: string, size: number, limit: number): string {
  const dropper = new LongStringDropper(limit)
  let out = ''
  for (let at = 0; at < text.length; at += size) out += dropper.push(text.slice(at, at + size))
  return out
}

test('long strings are emptied and everything else kept, however the text is split', () => {
  const text = JSON.stringify(map)
  const expected = { ...map, artwork: [{ filename: 'a.png', data: '' }] }
  for (const size of [1, 2, 3, 7, 64, text.length]) {
    assert.deepEqual(JSON.parse(inPieces(text, size, 100)), expected, `pieces of ${size}`)
  }
  assert.equal(inPieces(text, 5, 10_000), text)
})

test('a world map is known by its name or its first bytes', () => {
  assert.equal(isWorldMap('Session 2.world-map.json', ''), true)
  assert.equal(isWorldMap('old.hierarchical-map.json', ''), true)
  assert.equal(isWorldMap('export.json', '{"format": "marinara-hierarchical-map"'), true)
  assert.equal(isWorldMap('export.json', '{"locations": [{"id": "a", "parentId": null'), true)
  assert.equal(isWorldMap('my-city.json', '{"schema_version": 1, "id": "my-city"'), false)
})

test('a world map file is read without its pictures', async () => {
  const read = await readWorldMap(new Blob([JSON.stringify({ ...map, artwork: [{ data: 'B'.repeat(70_000) }] })]))
  assert.deepEqual((read as { artwork: unknown }).artwork, [{ data: '' }])
  await assert.rejects(readWorldMap(new Blob(['{"format": '])), /not readable JSON/)
})
