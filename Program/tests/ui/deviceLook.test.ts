import assert from 'node:assert/strict'
import { test } from 'node:test'
import { cleanLook, clampScale, clampWidth, DEFAULT_LOOK, GRID_WIDTH, PANEL_WIDTH } from '../../src/features/settings/deviceLook.ts'
import { shownScheme } from '../../src/features/settings/palette.ts'

test('text size stays between 85% and 200% in steps of 5', () => {
  assert.equal(clampScale(40), 85)
  assert.equal(clampScale(500), 200)
  assert.equal(clampScale(113), 115)
  assert.equal(clampScale(Number.NaN), 100)
})

test('a damaged saved look falls back to the defaults, keeping what is valid', () => {
  assert.deepEqual(cleanLook('nonsense'), DEFAULT_LOOK)
  assert.deepEqual(cleanLook({ textScale: 150, font: 'comic', motion: 'reduce', fontEverywhere: 'yes', layout: 'grid' }),
    { textScale: 150, font: 'default', fontEverywhere: false, motion: 'reduce', layout: 'classic', lastBeside: 'classic', stageArt: true, worldColors: true, panelWidth: 360, gridWidth: 600 })
  assert.equal(cleanLook({ layout: 'reader' }).layout, 'reader')
  assert.equal(cleanLook({ layout: 'custom' }).layout, 'custom')
  assert.equal(cleanLook({ lastBeside: 'custom' }).lastBeside, 'custom')
  assert.equal(cleanLook({ lastBeside: 'reader' }).lastBeside, 'classic')
  assert.equal(cleanLook({ layout: 'novel', lastBeside: 'novel' }).lastBeside, 'novel')
  assert.equal(cleanLook({ stageArt: false }).stageArt, false)
  assert.equal(cleanLook({ worldColors: false }).worldColors, false)
})

test('the panel beside the story keeps a dragged width within its bounds', () => {
  assert.equal(clampWidth(100, PANEL_WIDTH), PANEL_WIDTH.min)
  assert.equal(clampWidth(5000, PANEL_WIDTH), PANEL_WIDTH.max)
  assert.equal(clampWidth(412.6, PANEL_WIDTH), 413)
  assert.equal(clampWidth(Number.NaN, GRID_WIDTH), GRID_WIDTH.default)
  assert.equal(cleanLook({ panelWidth: 480, gridWidth: 'wide' }).panelWidth, 480)
  assert.equal(cleanLook({ panelWidth: 480, gridWidth: 'wide' }).gridWidth, GRID_WIDTH.default)
})

test('Match my computer shows Paper or Ink, and a saved scheme shows itself', () => {
  assert.equal(shownScheme({ theme: 'system', color_scheme: 'moss' }, true), 'paper')
  assert.equal(shownScheme({ theme: 'system', color_scheme: 'moss' }, false), 'ink')
  assert.equal(shownScheme({ theme: 'paper', color_scheme: 'moss' }, false), 'paper')
  assert.equal(shownScheme({ theme: 'scheme', color_scheme: 'moss' }, true), 'moss')
  assert.equal(shownScheme(undefined, false), 'ink')
})
