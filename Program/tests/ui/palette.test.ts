import assert from 'node:assert/strict'
import { test } from 'node:test'
import { COLOR_SCHEMES, defaultPalette, paletteReadability, paletteStyles, paperPalette, validPalette } from '../../src/features/settings/palette.ts'

test('the six Study schemes are offered, Ink first', () => {
  assert.deepEqual(COLOR_SCHEMES.map(scheme => scheme.id), ['ink', 'slate', 'umber', 'moss', 'wine', 'ash'])
})

test('a custom palette must be readable before it can be applied', () => {
  assert.ok(paletteReadability(defaultPalette).valid)
  assert.equal(paletteReadability({ ...defaultPalette, text: '#2a2a2a' }).valid, false)
  assert.equal(validPalette({ ...defaultPalette, accent: 'gold' }), false)
})

test('a custom palette sets the app variables, and a light background gets light form controls', () => {
  const styles = paletteStyles({ accent: '#7a4b00', background: '#fafafa', surface: '#ffffff', text: '#111111' })
  assert.equal(styles['--canvas'], '#fafafa')
  assert.equal(styles['color-scheme'], 'light')
  assert.equal(styles['--on-accent'], '#ffffff')
})

test('errors stay readable on a light custom palette', () => {
  assert.equal(paletteStyles(defaultPalette)['--danger'], '#e9b8aa')
  assert.equal(paletteStyles({ accent: '#7a4b00', background: '#fafafa', surface: '#ffffff', text: '#111111' })['--danger'], '#a3321f')
})

test('Paper is a starting point for a custom palette, and a light palette keeps its dialogs light', () => {
  assert.ok(paletteReadability(paperPalette).valid)
  const styles = paletteStyles(paperPalette)
  assert.equal(styles['--scheme'], 'light')
  assert.ok(styles['--input-border'])
  assert.equal(paletteStyles(defaultPalette)['--scheme'], 'dark')
})
