import assert from 'node:assert/strict'
import { test } from 'node:test'
import { themeStyle } from '../../src/features/story/worldTheme.ts'

const ember = { accent: '#c4623f', background: '#15110e', surface: '#1d1814', text: '#e8ddcb' }

test("a world's readable palette colors the story screen, scheme and all", () => {
  const style = themeStyle({ world: 'vallarith', theme: { name: 'Ember and soot', palette: ember } }, true) as Record<string, string>
  assert.equal(style['--canvas'], '#15110e')
  assert.equal(style['--accent'], '#c4623f')
  assert.equal(style.colorScheme, 'dark')
  assert.equal(style['color-scheme'], undefined)
})

test('no world colors when the player turned them off, the world has none, or they would not read', () => {
  assert.equal(themeStyle({ world: 'vallarith', theme: { name: 'Ember', palette: ember } }, false), undefined)
  assert.equal(themeStyle({ world: 'kingswood', theme: null }, true), undefined)
  assert.equal(themeStyle(undefined, true), undefined)
  const murky = { ...ember, text: '#2a2420' }
  assert.equal(themeStyle({ world: 'vallarith', theme: { name: 'Murk', palette: murky } }, true), undefined)
})
