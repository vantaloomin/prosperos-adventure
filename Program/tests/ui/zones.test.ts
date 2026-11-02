import { test } from 'node:test'
import assert from 'node:assert/strict'
import { COMMON_ZONES, allZones, commonZones, findZones, offsetText, zoneOf } from '../../src/features/settings/zoneText.ts'

const winter = new Date('2026-01-15T12:00:00Z')

test('a time zone reads as its city, its name and its offset', () => {
  assert.equal(zoneOf('America/Los_Angeles', winter).label, 'Los Angeles · Pacific Time (UTC−08:00)')
  assert.match(zoneOf('Asia/Kolkata', winter).label, /^Kolkata .*\(UTC\+05:30\)$/)
  assert.equal(zoneOf('UTC', winter).label, 'UTC (UTC)')
  assert.equal(offsetText(-570), 'UTC−09:30')
  assert.match(zoneOf('Asia/Calcutta', winter).label, /^Kolkata /)
  assert.ok(zoneOf('Asia/Calcutta', winter).search.includes('calcutta'))
})

test('zones run west to east and are found by city, name, region or offset', () => {
  const zones = allZones(['Asia/Tokyo', 'America/New_York', 'Europe/London'], ['America/New_York', 'Asia/Kolkata'], winter)
  assert.deepEqual(zones.map((zone) => zone.id), ['America/New_York', 'Europe/London', 'Asia/Kolkata', 'Asia/Tokyo'])
  assert.deepEqual(findZones(zones, 'tokyo').map((zone) => zone.id), ['Asia/Tokyo'])
  assert.deepEqual(findZones(zones, 'eastern').map((zone) => zone.id), ['America/New_York'])
  assert.deepEqual(findZones(zones, '+05:30').map((zone) => zone.id), ['Asia/Kolkata'])
  assert.deepEqual(findZones(zones, 'UTC−05').map((zone) => zone.id), ['America/New_York'])
  assert.equal(findZones(zones, '  ').length, 4)
  const pacific = findZones(allZones(['Pacific/Fiji', 'America/Los_Angeles'], [], winter), 'pacific')
  assert.deepEqual(pacific.map((zone) => zone.id), ['America/Los_Angeles', 'Pacific/Fiji'])
})

test('the common zones are real ones, shown only when listed', () => {
  assert.doesNotThrow(() => COMMON_ZONES.forEach((id) => new Intl.DateTimeFormat('en-US', { timeZone: id })))
  const zones = allZones(['Asia/Calcutta', 'Asia/Tokyo', 'America/Adak'], [], winter)
  assert.deepEqual(commonZones(zones).map((zone) => zone.id), ['Asia/Calcutta', 'Asia/Tokyo'])
})
