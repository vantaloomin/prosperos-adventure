import assert from 'node:assert/strict'
import { test } from 'node:test'
import { backupLabel, backupSize } from '../../src/features/settings/backupText.ts'

const iso = (value: string) => value.slice(0, 10)

test('sizes read in the largest sensible unit', () => {
  assert.equal(backupSize(200), '1 KB')
  assert.equal(backupSize(5 * 1024 * 1024), '5.0 MB')
  assert.equal(backupSize(3 * 1024 * 1024 * 1024), '3.00 GB')
})

test('labels say what a backup holds and mark pre-upgrade copies', () => {
  assert.equal(backupLabel({ name: 'dungeon-1.zip', bytes: 2048, kind: 'backup', readable: true, created_at: '2026-10-05T08:00:00Z' }, iso),
    'Backup, 2026-10-05 (2 KB)')
  assert.equal(backupLabel({ name: 'pre-upgrade-1.zip', bytes: 2048, kind: 'pre-upgrade', readable: true, created_at: '2026-10-04T08:00:00Z' }, iso),
    'Before an upgrade, 2026-10-04 (2 KB)')
  assert.equal(backupLabel({ name: 'before-delete-1.zip', bytes: 2048, kind: 'before-delete', readable: true, created_at: '2026-10-06T08:00:00Z' }, iso),
    'Before deleting, 2026-10-06 (2 KB)')
  assert.equal(backupLabel({ name: 'broken.zip', bytes: 9, kind: 'backup', readable: false }, iso), 'broken.zip (cannot be read)')
})
