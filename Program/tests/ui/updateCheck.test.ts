import assert from 'node:assert/strict'
import { test } from 'node:test'
import { howToUpdate, linkLabel, releasedOn } from '../../src/features/settings/updateText.ts'
import type { UpdateCheck } from '../../src/types.ts'

const found = (change: Partial<UpdateCheck>): UpdateCheck => ({
  status: 'newer', current: '0.1.0', latest: '0.2.0', title: null, published: null,
  page: 'https://github.com/vantaloomin/prosperos-adventure/releases/tag/v0.2.0', install: 'folder', system: 'windows', ...change,
})

test('a folder copy is pointed at its own update script', () => {
  assert.match(howToUpdate(found({})), /update\.bat in the Windows folder/)
  assert.match(howToUpdate(found({ system: 'mac' })), /update\.command in the Mac folder/)
  assert.match(howToUpdate(found({})), /^Close Adventure/)
})

test('the installed app is pointed at the new installer', () => {
  assert.match(howToUpdate(found({ install: 'installer' })), /^Download the new installer/)
})

test('the release date is left out when GitHub gave none', () => {
  assert.equal(releasedOn(null), '')
  assert.match(releasedOn('2026-11-03T13:30:00Z'), /^, released .*2026/)
})

test('the link says Download only for the installed app', () => {
  assert.equal(linkLabel(found({ install: 'installer' })), 'Download')
  assert.equal(linkLabel(found({})), 'What’s new')
  assert.equal(linkLabel(found({ status: 'current' })), 'What’s new in 0.1.0')
  assert.equal(linkLabel(found({ status: 'unavailable' })), 'Releases page')
})
