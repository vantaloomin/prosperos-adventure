import assert from 'node:assert/strict'
import { test } from 'node:test'
import { bookLine, entryHow, fileData, findEntries, timerLine, timingLine, type LoreBook, type LoreEntry } from '../../src/features/worlds/loreText.ts'

const entry = (changes: Partial<LoreEntry> = {}): LoreEntry => ({
  id: 'e', title: 'The Heartwood', text: 'An old forest the Guild wants felled.', keywords: ['heartwood', 'forest'], always: false, pattern: false,
  enabled: true, when: [], when_guessed: false, fits_now: false,
  timing: { sticky: 0, cooldown: 0, delay: 0, chance: 100, group_weight: 100, group: '' }, ...changes,
})

test('an entry says how it comes into the story', () => {
  assert.equal(entryHow(entry({ always: true })), 'Always in the story')
  assert.equal(entryHow(entry()), 'When someone says heartwood, forest')
  assert.equal(entryHow(entry({ when: [{ key: 'weather:rain', label: 'Rain' }] })), 'When someone says heartwood, forest, or when the scene fits: Rain')
  assert.equal(entryHow(entry({ keywords: [], when: [{ key: 'time:night', label: 'Night' }] })), 'When the scene fits: Night')
  assert.equal(entryHow(entry({ keywords: [] })), 'Never on its own')
})

test('a book line counts entries, the ones off and the ones always on', () => {
  const book: LoreBook = { id: 'b', name: 'Vallarith', description: '', source_format: '', source_file: '', city_id: null, enabled: true,
    entries: [entry(), entry({ enabled: false }), entry({ always: true })] }
  assert.equal(bookLine(book), '3 entries · 1 off · 1 always on')
})

test('entries are found by every word, in title, keywords or text', () => {
  const entries = [entry(), entry({ id: 'f', title: 'Gannet & Pryce', keywords: ['buyer'], text: 'A Guild buyer.' })]
  assert.deepEqual(findEntries(entries, 'guild BUYER').map((one) => one.id), ['f'])
  assert.equal(findEntries(entries, '  ').length, 2)
})

test('a file goes up as base64', async () => {
  assert.equal(await fileData(new Blob(['héllo'])), Buffer.from('héllo').toString('base64'))
})

test('an entry says its timing and where its timer stands', () => {
  assert.equal(timingLine(entry().timing), '')
  assert.equal(timingLine({ sticky: 1, cooldown: 3, delay: 5, chance: 40, group_weight: 10, group: 'mood' }),
    'Lingers 1 line · Rests 3 lines · Waits until line 5 · 40% chance · One of mood')
  assert.equal(timerLine(null), '')
  assert.equal(timerLine({ state: 'ready', lines: 0 }), '')
  assert.equal(timerLine({ state: 'resting', lines: 1 }), 'Resting for 1 more line')
  assert.equal(timerLine({ state: 'lingering', lines: 2 }), 'Lingering for 2 more lines')
})
