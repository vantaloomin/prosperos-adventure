import assert from 'node:assert/strict'
import { test } from 'node:test'
import { bandRates, buildShares, genderShares, pct, sameMix } from '../../src/features/settings/mixText.ts'

const defaults = { nonbinary: 6, women: 50, height_woman: 162, height_man: 176, slender: 37.5, middle: 37.5, heavier: 25, beard: 35, gay: 2.6, bisexual: 3, bolder: 0, drive: 0 }
const bands = [{ ages: '18 to 29', gay: 0.04, bisexual_women: 0.15, bisexual_men: 0.06 }, { ages: '60 and over', gay: 0.02, bisexual_women: 0.01, bisexual_men: 0.01 }]

test('the gender slider splits everyone who is not nonbinary', () => {
  assert.deepEqual(genderShares({ nonbinary: 6, women: 50 }), { woman: 47, man: 47, nonbinary: 6 })
  assert.deepEqual(genderShares({ nonbinary: 0, women: 100 }), { woman: 100, man: 0, nonbinary: 0 })
})

test('builds are shares of each other', () => {
  assert.deepEqual(buildShares({ slender: 1, middle: 1, heavier: 2 }), { slender: 25, middle: 25, heavier: 50 })
  assert.deepEqual(buildShares({ slender: 0, middle: 0, heavier: 0 }), { slender: 0, middle: 0, heavier: 0 })
})

test('orientation sliders scale every age band alike, as the server does', () => {
  const built = bandRates({ bands, defaults }, defaults)
  assert.equal(pct(built[0].gay), '4%')
  assert.equal(pct(built[0].bisexual), '10.5%')
  const doubled = bandRates({ bands, defaults }, { gay: 5.2, bisexual: 6 })
  assert.equal(pct(doubled[1].gay), '4%')
  // Never more than 95% of a band, whatever the sliders say.
  const most = bandRates({ bands, defaults }, { gay: 40, bisexual: 60 })
  assert.ok(most[0].gay + most[0].bisexual <= 95.0001)
})

test('a mix is the same when every value is', () => {
  assert.ok(sameMix({ ...defaults }, defaults))
  assert.ok(!sameMix({ ...defaults, beard: 40 }, defaults))
})

test('moving one build gives the others what is left, so the three make 100%', async () => {
  const { rebalanceBuilds } = await import('../../src/features/settings/mixText.ts')
  const moved = rebalanceBuilds(defaults, 'heavier', 50)
  assert.deepEqual([moved.slender, moved.middle, moved.heavier], [25, 25, 50])
  const all = rebalanceBuilds({ ...defaults, slender: 0, middle: 0, heavier: 100 }, 'heavier', 40)
  assert.equal(all.slender + all.middle + all.heavier, 100)
})

test('the confirmation and screen readers say what the sliders say', async () => {
  const { changesLine, valueText } = await import('../../src/features/settings/mixText.ts')
  assert.equal(changesLine({ ...defaults, heavier: 50, slender: 25, middle: 25, height_man: 183 }, defaults),
    'taller men, fewer slender builds, fewer in-between builds, more heavier builds')
  assert.equal(valueText('height_woman', 162), '5 foot 4, 162 cm')
  assert.equal(valueText('slender', 30), '30 percent slender')
  assert.equal(valueText('bolder', 1, { '1': 'Bolder' }), 'Bolder')
})
