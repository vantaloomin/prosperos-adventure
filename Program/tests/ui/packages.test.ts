import { test } from 'node:test'
import assert from 'node:assert/strict'
import { hiddenLine, hiddenTotal, nameFromFiles, packageLine, parseEntries, statusLine } from '../../src/features/worlds/packagesText.ts'

const summary = { id: 'ashmoor', name: 'Ashmoor', builtin: false, documents: 2, engine: 0, assets: 0,
  sections: { cast: { entries: 3, hidden: 1 }, lore: { entries: 12, hidden: 0 }, regions: { entries: 0, hidden: 0 } } }

test('a package says what it holds, biggest first, and how much is hidden', () => {
  assert.equal(packageLine(summary), 'Lore 12 · Cast 3 · 2 documents')
  assert.equal(packageLine({ ...summary, sections: {}, documents: 0 }), 'Empty')
  assert.equal(hiddenTotal(summary), 1)
})

test('a section says where its draft came from and warns of hidden truths', () => {
  const entries = [{ id: 'old-tam' }, { id: 'jess' }]
  assert.equal(statusLine({ id: 'lore', status: 'drafted', from: 'lorebook', entries, hidden: 0 }), 'Drafted from your lorebook, ready for you to read · 2 entries')
  assert.equal(statusLine({ id: 'cast', status: 'approved', from: 'model', entries: entries.slice(1), hidden: 0 }), 'Approved · 1 entry')
  assert.equal(statusLine({ id: 'cast', status: 'empty', from: '', entries: [], hidden: 0 }), 'Not drafted')
  assert.equal(hiddenLine({ id: 'cast', hidden: 1, entries }), '1 entry holds a hidden truth (a secret field). The player never sees it.')
  assert.equal(hiddenLine({ id: 'hidden-truths', hidden: 2, entries }), 'Every entry here is hidden from the player.')
  assert.equal(hiddenLine({ id: 'cast', hidden: 0, entries }), '')
})

test('edited entries must be a JSON list of objects', () => {
  assert.deepEqual(parseEntries('[{"id": "old-tam"}]'), { entries: [{ id: 'old-tam' }] })
  assert.match((parseEntries('{"id": "old-tam"}') as { error: string }).error, /list of entries/)
  assert.match((parseEntries('[{"id": "a"}, 3]') as { error: string }).error, /Entry 2/)
  assert.match((parseEntries('[{') as { error: string }).error, /not valid JSON/)
})

test('a world is named from its first file until the author names it', () => {
  assert.equal(nameFromFiles(['ashmoor-overview.md']), 'Ashmoor overview')
  assert.equal(nameFromFiles([]), '')
})
