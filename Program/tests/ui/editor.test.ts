import { test } from 'node:test'
import assert from 'node:assert/strict'
import { changeLine, entryFrom, formFields, idFrom, kindOf, listingQuery, parseEntry } from '../../src/features/worlds/editorText.ts'

test('an entry becomes form fields by the kind of each value, id first, hidden truths marked', () => {
  const fields = formFields({ name: 'Old Tam', id: 'old-tam', age: 70, dead: false, secret: 'He drowned the miller.', ties: ['jess'] })
  assert.deepEqual(fields.map((field) => [field.key, field.kind, field.hidden]), [
    ['id', 'line', false], ['name', 'line', false], ['age', 'number', false], ['dead', 'switch', false],
    ['secret', 'line', true], ['ties', 'json', false]])
  assert.equal(kindOf('a'.repeat(81)), 'text')
  assert.ok(formFields({ id: 'x', text: 'y' }, 'hidden-truths').every((field) => field.hidden))
})

test('the form reads back into the same entry, and names a field that will not read', () => {
  const entry = { id: 'old-tam', age: 70, dead: true, ties: ['jess'], note: 'two\nlines' }
  assert.deepEqual(entryFrom(formFields(entry)), { entry })
  const broken = formFields(entry).map((field) => field.key === 'ties' ? { ...field, text: '[jess' } : field)
  assert.deepEqual(entryFrom(broken), { error: 'ties is not valid JSON: check its brackets and commas.' })
  const nan = formFields(entry).map((field) => field.key === 'age' ? { ...field, text: 'old' } : field)
  assert.deepEqual(entryFrom(nan), { error: 'age must be a number.' })
})

test('the raw view takes one object, ids come from names, and the listing asks for its filters', () => {
  assert.deepEqual(parseEntry('{"id": "a"}'), { entry: { id: 'a' } })
  assert.deepEqual(parseEntry('[1]'), { error: 'An entry is one object, in { }.' })
  assert.equal(idFrom('  Édith of the Ford! '), 'edith-of-the-ford')
  assert.equal(listingQuery('cast', ' Ilvar ', 'hidden'), '?section=cast&q=Ilvar&hidden=true')
  assert.equal(listingQuery('', '', 'all'), '')
  assert.equal(changeLine({ id: 1, at: '', section: 'cast', entry_id: 'jess', change: 'deleted' }), 'Deleted jess in Cast')
})
