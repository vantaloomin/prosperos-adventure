import assert from 'node:assert/strict'
import { test } from 'node:test'
import { isView, navCurrent } from '../../src/features/nav/navText.ts'

test('the address names the story, worlds or a settings tab, and anything else opens the story', () => {
  for (const view of ['story', 'worlds', 'settings', 'settings/models']) assert.equal(isView(view), true, view)
  for (const view of ['conversation', 'today', 'chats', 'map/abc', '']) assert.equal(isView(view), false, view)
})

test('Settings stays lit on every settings tab', () => {
  assert.equal(navCurrent('settings', 'settings/debug'), true)
  assert.equal(navCurrent('story', 'story'), true)
  assert.equal(navCurrent('story', 'settings'), false)
})
