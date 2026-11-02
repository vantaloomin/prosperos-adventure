import assert from 'node:assert/strict'
import { test } from 'node:test'
import { milestone, navLabel, progressLine, quality, roomy, size, timeLeft, type ReadyView } from '../../src/features/ready/readyText.ts'
const pick = { key: 'qwen3.5-9b', name: 'Qwen3.5 9B', quant: 'Q4_K_M', bits: '4-bit', bytes: 5_680_522_464, file: 'x.gguf', licence: 'Apache 2.0', page: '', fits: true }
const view = (change: Partial<ReadyView> = {}): ReadyView => ({
  pick, reason: '', models: [pick], runtime: { installed: false }, runtime_bytes: 33_377_746, card: { name: 'RTX 4070', memory_gb: 12 },
  status: 'idle', model: null, received: 0, total: 0, message: '', waiting: false, seconds_left: null, free_bytes: 300e9, drive: 'Z:',
  in_use: false, profile_id: null, announced: false, settings_seen: false, ...change,
})

test('sizes and time left are rounded so they never flicker', () => {
  assert.equal(size(5_680_522_464), '5.7 GB')
  assert.equal(size(33_377_746), '33 MB')
  assert.equal(timeLeft(null), '')
  assert.equal(timeLeft(70), 'about a minute')
  assert.equal(timeLeft(7 * 60), 'about 7 minutes')
  assert.equal(timeLeft(38 * 60), 'about 40 minutes')
  assert.equal(timeLeft(70 * 60), 'about 1 hour')
  assert.equal(timeLeft(150 * 60), 'about 2.5 hours')
})

test('the quant code comes with plain words', () => {
  assert.equal(quality('Q8_0'), 'high quality')
  assert.equal(quality('Q4_K_M'), 'balanced')
  assert.equal(quality('Q3_K_S'), 'smaller and faster')
})

test('the progress line says how far, how long, or why it is waiting', () => {
  const going = view({ status: 'downloading', model: pick.key, received: 3.2e9, total: 5.7e9, seconds_left: 720 })
  assert.equal(progressLine(going), '3.2 of 5.7 GB · about 10 minutes left')
  assert.equal(progressLine({ ...going, waiting: true }), 'Waiting for the connection… 3.2 of 5.7 GB')
  assert.equal(navLabel(going), 'Settings, model downloading, 56%')
  assert.equal(milestone(56), 50)
})

test('there must be room for the model and the runtime', () => {
  assert.ok(roomy(view()))
  assert.equal(roomy(view({ free_bytes: 6e9 })), false)
})
