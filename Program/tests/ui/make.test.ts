import assert from 'node:assert/strict'
import { test } from 'node:test'
import { emptyForm, filledLine, madeBody, memberBody, memberReady, moved, newMember, newSeed, picksOf, released, sameSliders, setLooks, sheetBody, withDraft } from '../../src/features/make/makeText.ts'

const draft = { name: 'Wren Ashdown', gender: 'woman' as const, age: 34, about: 'A barge pilot.', look: 'Rope-burned wrist.', voice: 'Short.', wants: 'Clear her debt.', fears: 'Losing the barge.' }

test('a draft fills the fields and keeps the rolled extras', () => {
  const form = { ...emptyForm('seed'), seen_as: 'Blunt.', personality_sliders: { warmth: { level: 0 as const, source: 'you' as const } } }
  const filled = withDraft(form, draft)
  assert.equal(filled.name, 'Wren Ashdown')
  assert.equal(filled.age, '34')
  assert.equal(filled.seen_as, 'Blunt.')
  assert.deepEqual(filled.personality_sliders, form.personality_sliders)
  // A split that gives no name or age keeps the ones typed.
  const kept = withDraft({ ...form, name: 'Mine', age: '40' }, { ...draft, name: '', age: null })
  assert.equal(kept.name, 'Mine')
  assert.equal(kept.age, '40')
})

test('the quick start sends what the form already says, and the idea', () => {
  assert.deepEqual(picksOf({ ...emptyForm('s'), name: ' Wren ', age: '34' }, ' barge pilot '), { name: 'Wren', gender: '', age: 34, idea: 'barge pilot' })
  assert.deepEqual(picksOf(emptyForm('s'), ''), { name: '', gender: '', idea: '' })
  assert.deepEqual(picksOf(emptyForm('s'), '', true), { name: '', gender: '', idea: '', party: true })
})

test('Begin sends only the Looks the person set, and the seed the form rolled with', () => {
  const form = { ...emptyForm('abc'), look: ' Tall. ', looks: { hair: 'red', eyes: '', height_cm: null, weight_kg: 70 } }
  assert.deepEqual(setLooks(form.looks), { hair: 'red', weight_kg: 70 })
  const body = madeBody(form)
  assert.equal(body.seed, 'abc')
  assert.equal(body.look, 'Tall.')
  assert.equal('personality_sliders' in body, false)
  assert.deepEqual(sheetBody({ ...form, name: 'W', age: '30' }).age, 30)
})

test('sliders: a moved one is the person\'s, a released one goes back to the roll', () => {
  const sliders = moved({}, 'warmth', 2.4)
  assert.deepEqual(sliders, { warmth: { level: 2, source: 'you' } })
  assert.deepEqual(released(sliders, 'warmth'), {})
  assert.equal(sameSliders(sliders, { warmth: { level: 2, source: 'you' } }), true)
  assert.equal(sameSliders(sliders, { warmth: { level: 2, source: 'rolled' } }), false)
})

test('a split names the fields it wrote, and seeds are short and plain', () => {
  assert.equal(filledLine(['fears', 'voice', 'nonsense']), 'Written for you: Fears, Voice')
  assert.equal(filledLine([]), '')
  assert.match(newSeed(), /^[a-z0-9]{12}$/)
})

test('a party member you make needs a name, an adult age or none, and says how they decide', () => {
  const member = newMember('made-1')
  assert.equal(member.mind, 'agent')
  assert.equal(memberReady(member), false)
  const named = { ...member, form: { ...member.form, name: ' Tamsin ', about: ' Keeps the lock. ' }, mind: 'program' as const }
  assert.equal(memberReady(named), true)
  assert.equal(memberReady({ ...named, form: { ...named.form, age: '16' } }), false)
  const body = memberBody({ ...named, form: { ...named.form, age: '41' } })
  assert.equal(body.name, 'Tamsin')
  assert.equal(body.age, 41)
  assert.equal(body.about, 'Keeps the lock.')
  assert.equal(body.mind, 'program')
  assert.equal(body.seed, member.form.seed)
  assert.equal('age' in memberBody(named), false)
})
