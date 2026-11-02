import assert from 'node:assert/strict'
import { test } from 'node:test'
import { bounded, countText, hoursText, minutesText, presetOptions } from '../../src/components/numberBounds.ts'

test('a number box never holds more than its most', () => {
  assert.equal(bounded('61478156156', 0, 6), '6')
  assert.equal(bounded('4', 0, 6), '4')
  assert.equal(bounded('1e9', 0, 6), '6')
})

test('the least is enforced only when leaving the box, so 15 can be typed through 1', () => {
  assert.equal(bounded('1', 15, 1440), '1')
  assert.equal(bounded('1', 15, 1440, true), '15')
  assert.equal(bounded('-3', 0, 24, true), '0')
})

test('blank and half-typed values are left alone', () => {
  assert.equal(bounded('', 0, 6, true), '')
  assert.equal(bounded('-', -2, 2), '-')
  assert.equal(bounded('9', undefined, undefined, true), '9')
})

test('counts and time spans read in words', () => {
  assert.equal(countText(0, 'event', 'events', 'None'), 'None')
  assert.equal(countText(1, 'event', 'events'), '1 event')
  assert.equal(hoursText(336), '2 weeks')
  assert.equal(hoursText(48), '2 days')
  assert.equal(hoursText(5), '5 hours')
  assert.equal(minutesText(90), '90 minutes')
  assert.equal(minutesText(1440), '1 day')
})

test('a saved value that is not a preset stays listed in order', () => {
  assert.deepEqual(presetOptions([1, 2, 4], 3, hoursText).map(option => option.label), ['1 hour', '2 hours', '3 hours', '4 hours'])
  assert.deepEqual(presetOptions([1, 2, 4], 2, hoursText).map(option => option.value), [1, 2, 4])
})
