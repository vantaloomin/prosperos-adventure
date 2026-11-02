import { test } from 'node:test'
import assert from 'node:assert/strict'
import { appNow, realDelay, syncAppClock } from '../../src/appTime.ts'
import { bannerText, formatAppTime } from '../../src/features/settings/debugText.ts'

test('the app clock is real time until debug time moves it, then runs at its speed', () => {
  syncAppClock({ active: false, now: '2020-01-01T00:00:00Z', speed: 1 })
  assert.ok(Math.abs(appNow() - Date.now()) < 50)
  assert.equal(realDelay(60_000), 60_000)
  syncAppClock({ active: true, now: '2030-05-01T12:00:00Z', speed: 60 })
  assert.ok(Math.abs(appNow() - Date.parse('2030-05-01T12:00:00Z')) < 60 * 50)
  assert.equal(realDelay(60_000), 1000)
  syncAppClock({ active: false, now: '2020-01-01T00:00:00Z', speed: 1 })
})

test('the banner says it is debug time, how fast, and how a jump is going', () => {
  const now = '2026-10-08T13:30:00Z'
  assert.match(bannerText({ now, speed: 1, jumping: null }, 'UTC'), /^Debug time: it is .*1:30.* in the app\. Return to real time/)
  assert.match(bannerText({ now, speed: 60, jumping: null }, 'UTC'), /running 60× fast/)
  assert.match(bannerText({ now, speed: 1, jumping: { to: now, done: 0.42 } }, 'UTC'), /jumping ahead to .*\(42%\)/)
  assert.equal(formatAppTime(now, 'Not/AZone'), formatAppTime(now))
})
