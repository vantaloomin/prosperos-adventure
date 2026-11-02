import assert from 'node:assert/strict'
import test from 'node:test'
import { asKindOption, foundOption, humanTermsText, kindSummary, lifeAge, longLived, pickedLifespan, spanChoices, yearsText } from '../../src/features/kinds/kindText.ts'
import { ageHint } from '../../src/features/worlds/worldsText.ts'
import type { KindShown } from '../../src/types.ts'

const elf: KindShown = { kind: 'elf', label: 'Elf', own: null, years: 600, kind_years: 600, life_age: 49 }

test('the kind pickers name the app pick and the kind lifespan first', () => {
  assert.equal(foundOption('Elf', 'words'), 'As their description says (Elf)')
  assert.equal(foundOption('Half-elf', 'parents'), 'From their parents (Half-elf)')
  assert.equal(foundOption('Human', 'app'), 'As the app picks (Human)')
  assert.equal(asKindOption(600), 'As their kind (about 600 years)')
  assert.equal(asKindOption(null), "As their kind (doesn't age)")
  assert.equal(yearsText(1000), '1,000 years')
})

test('the age in human terms shows only when it differs', () => {
  assert.equal(humanTermsText(elf, 312), 'About 49 in human terms.')
  assert.equal(humanTermsText({ ...elf, life_age: null }, 34), '')
  assert.equal(humanTermsText({ ...elf, life_age: 12 }, 12), '')
})

test('a picked lifespan not on the list stays offered', () => {
  assert.deepEqual(spanChoices({ kinds: [], spans: [80, 600] }, 450), [80, 450, 600])
  assert.deepEqual(spanChoices(undefined, null), [80, 150, 300, 600, 1000])
})

test('a folded kind section sums itself up', () => {
  assert.equal(kindSummary(elf), 'Kind: Elf · lives about 600 years')
  assert.equal(kindSummary({ ...elf, own: 0, years: null }), "Kind: Elf · doesn't age")
  assert.equal(kindSummary({ ...elf, kind: 'ageless', label: "Doesn't age", years: null }), "Kind: Doesn't age")
})

test('on the Persona page the pickers speak to you', () => {
  assert.equal(foundOption('Elf', 'words', true), 'As About you says (Elf)')
  assert.equal(asKindOption(600, true), 'As your kind (about 600 years)')
  assert.equal(asKindOption(null, true), "As your kind (doesn't age)")
})

test('life age in the browser matches the rules', () => {
  assert.equal(lifeAge(300, 600), 48)
  assert.equal(lifeAge(312, 600), 49)
  assert.equal(lifeAge(40, 80), 40)
  assert.equal(lifeAge(300, null), 300)
  const choices = { kinds: [{ id: 'elf', label: 'Elf', lifespan: 600 }, { id: 'halfling', label: 'Halfling', lifespan: 110 }, { id: 'ageless', label: "Doesn't age", lifespan: null }], spans: [80, 600] }
  assert.equal(pickedLifespan(choices, 'elf', null, 80), 600)
  assert.equal(pickedLifespan(choices, '', null, 600), 600)
  assert.equal(pickedLifespan(choices, 'elf', 0, 80), null)
  assert.equal(pickedLifespan(choices, 'ageless', null, 80), null)
  assert.equal(pickedLifespan(choices, 'halfling', 1000, 80), 1000)
  assert.ok(longLived(600) && longLived(null) && longLived(180))
  assert.ok(!longLived(110) && !longLived(150) && !longLived(80))
})

test('a persona age is typed: adults only, to 120, and to 5,000 only for a long-lived kind', () => {
  assert.match(ageHint(17, false) ?? '', /adult/)
  assert.equal(ageHint(18, false), undefined)
  assert.equal(ageHint(120, false), undefined)
  assert.match(ageHint(30.5, false) ?? '', /whole years/)
  assert.match(ageHint(5001, true) ?? '', /5,000/)
  assert.equal(ageHint(5000, true), undefined)
  assert.equal(ageHint(null, false), undefined)
  assert.match(ageHint(300, false) ?? '', /long-lived kind/)
  assert.equal(ageHint(300, true), undefined)
  assert.equal(ageHint(90, false), undefined)
})
