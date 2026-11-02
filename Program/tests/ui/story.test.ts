import assert from 'node:assert/strict'
import { test } from 'node:test'
import { actionLine, aroundText, diceFaces, diceNotation, tumbleFace, bandSpans, branchLine, journeyTo, markerAt, nearMiss, NO_TURN, turnAfter, reworded, sentences, foesText, zoneText, tallyText, statusItems, haggleText, paceText, intensityChoices, dramaChoices, gearLine, looksText, journalKind, moneyText, questState, slotsText, personLine, placeGroups, pointsLeft, pointsText, premadeLine, rollText, rollWhat, unrolled, fateFaces, fateLadder, challengeDice, brpCost, xpLine, spellLine, sceneTime, abilityLine, signed, arrayPlaced, skillChoices, skillId, startingStats, tierText, darkText, bondsText, bondLine, threadKind, otherTowns, receiptsByReply, institutionLine, todayLine, toggledVeil } from '../../src/features/story/storyText.ts'
import { artLabel, artStatus, making, pictureChoices } from '../../src/features/story/artText.ts'

test('the scene time is the city clock as written', () => {
  assert.equal(sceneTime('2026-10-06T09:05'), 'Tuesday, 9:05 am')
  assert.equal(sceneTime('2026-10-06T00:30'), 'Tuesday, 12:30 am')
  assert.equal(sceneTime('2026-10-06T21:40'), 'Tuesday, 9:40 pm')
})

test('who is around reads as a sentence', () => {
  assert.equal(aroundText([]), 'Nobody you would notice is here.')
  assert.equal(aroundText(['the barista']), 'The barista is here.')
  assert.equal(aroundText(['the barista', 'a regular', 'a neighbor']), 'The barista, a regular and a neighbor are here.')
})

test('unnamed people who read the same are counted, not repeated', () => {
  const local = (hood: string) => `a local from ${hood}`
  assert.equal(aroundText(['the barista', local('Little Italy'), local('Little Italy'), local('Harbor East'), local('Little Italy'), local('Fells Point')]),
    'The barista, three locals from Little Italy, a local from Harbor East and a local from Fells Point are here.')
  assert.equal(aroundText([local('Canton'), local('Canton')]), 'Two locals from Canton are here.')
  assert.equal(aroundText(['a neighbor waiting for the bus', 'a neighbor waiting for the bus']), 'Two neighbors waiting for the bus are here.')
  assert.equal(aroundText(['the barista', 'the barista', 'the waitress', 'the waitress']), 'Two baristas and two waitresses are here.')
  assert.equal(aroundText(['Dana, the barista', 'Dana, the barista']), 'Dana, the barista and Dana, the barista are here.')
  // A role of several words takes the plural on its head noun, its last word.
  assert.equal(aroundText(["a head chef at Joe's", "a head chef at Joe's"]), "Two head chefs at Joe's are here.")
  assert.equal(aroundText(['a line cook', 'a line cook', 'a delivery man', 'a delivery man']), 'Two line cooks and two delivery men are here.')
})

test('places are grouped by neighborhood', () => {
  const place = (id: string, neighborhood: string) => ({ id, name: id, kind: 'cafe', neighborhood })
  assert.deepEqual(placeGroups([place('b', 'Canton'), place('a', 'Fells Point'), place('c', 'Canton')]).map(([hood, items]) => [hood, items.map((item) => item.id)]),
    [['Canton', ['b', 'c']], ['Fells Point', ['a']]])
})

test('a person met says how often and where they are now', () => {
  const person = { key: 'k', name: 'Dana Kim', role: 'barista', city: 'Baltimore', meetings: 3, last_met_at: '', notes: [],
    doing: 'working as the barista', place: { id: 'p', name: 'The Daily Grind', city_id: 'baltimore' }, feelings: '' }
  assert.equal(personLine(person), 'Met 3 times · now working as the barista at The Daily Grind')
  assert.equal(personLine({ ...person, meetings: 1, doing: 'at home', place: null }), 'Met once · now at home')
  assert.equal(personLine({ ...person, doing: 'at their usual spot at The Daily Grind' }), 'Met 3 times · now at their usual spot at The Daily Grind')
})

test('a shown roll reads as the sum it was', () => {
  const roll = { action: 'x', stat: 'Allure', difficulty: 'very_hard', die: 8, natural: 62, bonus: 5, shift: 20, total: 47, band: 'failure_upside' as const, label: 'Fail with an upside' }
  assert.equal(rollText(roll), 'Allure d8: 62 + 5, very hard (-20) = 47, Fail with an upside')
  assert.equal(rollText({ ...roll, die: null, bonus: 0, shift: -10, difficulty: 'easy', total: 72, label: 'Success' }), 'Allure: 62, easy (+10) = 72, Success')
  assert.equal(rollText({ ...roll, shift: 0, difficulty: 'normal', total: 67, label: 'Success at a cost' }), 'Allure d8: 62 + 5 = 67, Success at a cost')
})

test('a made character starts even and counts the points it has left', () => {
  const start = { stat_names: ['Mind', 'Allure', 'Resolve', 'Vitality', 'Essence', 'Luck'], points: 60, range: [4, 18] as [number, number] }
  const stats = startingStats(start)
  assert.deepEqual(Object.values(stats), [10, 10, 10, 10, 10, 10])
  assert.equal(pointsLeft(stats, 60), 0)
  assert.equal(pointsLeft({ ...stats, Mind: 13 }, 60), -3)
  assert.equal(pointsText(-1, 60), '1 point over of 60')
  assert.equal(pointsText(4, 60), '4 points left of 60')
  assert.equal(premadeLine({ gender: 'woman', age: 41 }), 'a woman, 41')
  assert.equal(premadeLine({ gender: 'nonbinary', age: null }), 'nonbinary')
  assert.equal(premadeLine({ gender: '', age: null }), '')
})

test('a branch says how long it ran', () => {
  assert.equal(branchLine({ turns: 1, last_at: '' }), '1 turn')
  assert.match(branchLine({ turns: 3, last_at: '2026-10-21T20:00:00' }), /^3 turns, last played /)
})

test('a journal line names its kind and what it is about', () => {
  assert.equal(journalKind({ kind: 'wound', subject: 'you', truth: 'both' }), 'Wound · you')
  assert.equal(journalKind({ kind: 'secret', subject: 'Gus', truth: 'belief' }), 'Secret · Gus (you believe)')
})

test('a quest shows the time left, or how it ended', () => {
  assert.equal(questState({ status: 'open', left: 'about 7 days left' }), 'Underway · about 7 days left')
  assert.equal(questState({ status: 'open', left: '' }), 'Underway')
  assert.equal(questState({ status: 'missed', left: '' }), 'Too late')
  assert.equal(questState({ status: 'open', left: '3 days left', kind: 'oath' }), 'Oath · Underway · 3 days left')
  assert.equal(questState({ status: 'done', left: '', kind: 'job' }), 'Job · ' + questState({ status: 'done', left: '' }))
})

test('money, gear and slots read plainly', () => {
  assert.equal(moneyText(340, { code: 'crown', symbol: 'cr.' }), '3.40 cr.')
  assert.equal(moneyText(5, { code: 'crown', name: 'silver crowns' }), '0.05 silver crowns')
  assert.equal(gearLine({ name: 'Rope, fifty feet', qty: 2 }), 'Rope, fifty feet × 2')
  assert.equal(gearLine({ name: 'Belt knife', qty: 1 }), 'Belt knife')
  assert.equal(gearLine({ name: 'Signet ring', qty: 1, stolen: true }), 'Signet ring (stolen)')
  assert.equal(slotsText({ used: 2.5, max: null }), '2.5 slots, no limit')
  assert.equal(looksText({ cleanliness: 'grimy (blood, mud)', grime: 'grimy', marks: ['blood', 'mud'], clothes: 'torn', dress: { outer: 'off (the Felled Oak)' }, on_show: ['Plain sword'] }),
    'Grimy (blood, mud); clothes torn; outer clothing off (the Felled Oak); on show: Plain sword')
  assert.equal(slotsText({ used: 3.35, max: 13 }), '3.35 of 13 slots')
  assert.equal(slotsText({ used: 2.5, max: 10 }), '2.5 of 10 slots')
})

test('tallyText counts the rolls and how many landed', () => {
  assert.equal(tallyText({ rolls: 0, landed: 0, bands: {} }), 'No rolls yet.')
  assert.equal(tallyText({ rolls: 1, landed: 1, bands: { success: 1 } }), '1 roll, 1 landed (100%)')
  assert.equal(tallyText({ rolls: 14, landed: 9, bands: {} }), '14 rolls, 9 landed (64%)')
})

test('zoneText says how far off a foe is', () => {
  assert.equal(zoneText('engaged'), '')
  assert.equal(zoneText(undefined), '')
  assert.equal(zoneText('near'), ' · nearby')
  assert.equal(zoneText('far'), ' · far off')
})

test('foesText names who the character is fighting, or that they are dead', () => {
  assert.equal(foesText({ condition: 'grazed', dead: false, fight: null }), '')
  assert.equal(foesText({ condition: 'grazed', dead: false, fight: { round: 1, foes: [
    { name: 'the bandit', state: 'hurt', wound: null }, { name: 'the lookout', state: 'broken', wound: null }] } }),
  'Fighting: the bandit (hurt), the lookout (broken).')
  assert.equal(foesText({ condition: 'unhurt', dead: false, fight: { round: 1, foes: [{ name: 'the boar', state: 'hurt', wound: 2 }] } }),
    'Fighting: the boar (hurt, wound 2 of 5).')
  assert.match(foesText({ condition: 'dying', dead: true, fight: null }), /dead/)
  // Under 5E, with the dice shown, the foes' hit points.
  assert.equal(foesText({ condition: 'hurt', dead: false, fight: { round: 1, foes: [{ name: 'the bandit', state: 'grazed', wound: 1, hp: 9, max_hp: 11 }] } }),
    'Fighting: the bandit (grazed, 9 of 11 HP).')
})

test('statusItems puts how things stand in a few words', () => {
  const scene = { local_time: '1290-05-01T20:44:00', weather: 'rain' }
  const texts = (fight: Parameters<typeof statusItems>[1], coin: string | null = '3.40 cr.') => statusItems(scene, fight, coin).map((item) => item.text)
  assert.deepEqual(texts({ condition: 'unhurt', dead: false, fight: null }).slice(1), ['Unhurt', 'Nerve: steady', '3.40 cr.'])
  assert.deepEqual(texts({ condition: 'hurt', dead: false, fight: null, hp: 6, max_hp: 12, stress: 'strained, 5 of 12', injuries: ['a limp', 'nightmares'], captors: 'the wardens' }, null).slice(1),
    ['Hurt, 6 of 12 HP', 'Nerve: strained, 5 of 12', 'Lasting: a limp, nightmares', 'Held by the wardens'])
  assert.deepEqual(texts({ condition: 'dying', dead: true, fight: null }).slice(1), ['Dead'])
  assert.match(texts({ condition: 'unhurt', dead: false, fight: null })[0], / · rain$/)
})

test('intensityChoices offers the world\'s own preset first, by name', () => {
  const choices = intensityChoices('unflinching')
  assert.deepEqual(choices[0], ['world', "The world's own (Unflinching)"])
  assert.deepEqual(choices.map(([value]) => value), ['world', 'restrained', 'mature', 'unflinching'])
})

test('dramaChoices offers the world\'s own level first, by name', () => {
  const choices = dramaChoices('eventful')
  assert.deepEqual(choices[0], ['world', "The world's own (Eventful)"])
  assert.deepEqual(choices.map(([value]) => value), ['world', 'quiet', 'uneasy', 'eventful', 'merciless'])
})

test('haggleText says how a haggle moved today\'s prices', () => {
  assert.equal(haggleText(-15), '15% off today')
  assert.equal(haggleText(20), '20% dearer today')
  assert.equal(haggleText(0), '')
})

test('paceText says how long a turn took, its slowest step and what gave way', () => {
  assert.equal(paceText({ steps: { referee: 0.4, narrator: 9.84 }, skipped: [], budget: 30, total: 10.3 }),
    'Took 10.3 s of 30 · narrator 9.8 s')
  assert.equal(paceText({ steps: { narrator: 41 }, skipped: ['rewrite', 'contradiction'], budget: 30, total: 41.2 }),
    'Took 41.2 s of 30 · narrator 41.0 s · skipped the prose rewrite and the contradiction check for time')
})

test('the tier reads in words, with its numbers only when the dice are shown', () => {
  const tier = { tier: 'Local', words: 'known on their own street', track: 'Renown', arc: 'classic' as const, pace: 'steady' as const }
  assert.equal(tierText(tier), 'Renown: Local, known on their own street')
  assert.equal(tierText({ ...tier, points: 3, next: 12 }), 'Renown: Local, known on their own street (3 of 12)')
  assert.equal(tierText({ ...tier, tier: 'Mythic', points: 200, next: null }), 'Renown: Mythic, known on their own street (200)')
})

test('a dark track reads as a word, with its points when the dice are shown', () => {
  const track = { id: 'corruption', name: 'Corruption', word: 'tainted', changes: [] }
  assert.equal(darkText(track), 'Corruption: tainted')
  assert.equal(darkText({ ...track, points: 4, top: 10 }), 'Corruption: tainted (4 of 10)')
})

test('the Bonds track reads as a word, with the count when the dice are shown, and names each bond', () => {
  assert.equal(bondsText({ word: 'one true bond', bonds: [] }), 'Bonds: one true bond')
  assert.equal(bondsText({ word: 'one true bond', count: 1, bonds: [] }), 'Bonds: one true bond (1)')
  assert.equal(bondLine({ key: 'h', name: 'Hesk Aldane', how: 'sworn', state: 'whole' }), 'Hesk Aldane (sworn)')
  assert.equal(bondLine({ key: 'h', name: 'Hesk Aldane', how: 'earned', state: 'lost' }), 'Hesk Aldane (earned, lost)')
})

test('a loose end in the journal says what kind it is', () => {
  assert.equal(threadKind('mystery'), 'A mystery')
  assert.equal(threadKind('grudge'), 'A grudge')
})

test('journeyTo finds a destination on the travel map, ignoring a leading "the" and case', () => {
  const journeys = ['Eriane', 'the Abandoned Keep']
  assert.equal(journeyTo(journeys, 'eriane'), 'Eriane')
  assert.equal(journeyTo(journeys, 'Abandoned Keep'), 'the Abandoned Keep')
  assert.equal(journeyTo(journeys, 'The Green'), undefined)
  assert.equal(journeyTo(journeys, undefined), undefined)
})

test('sentences splits a paragraph and keeps closing quotes with their sentence', () => {
  assert.deepEqual(sentences('She waits. "You\'ll want the cellar." He nods'), ['She waits. ', '"You\'ll want the cellar." ', 'He nods'])
})

test('reworded marks only sentences whose words changed after streaming', () => {
  const draft = 'The stew has gone to skin — nobody wants it.\n\nShe wipes the bar. It is clean already.'
  const saved = 'The stew has gone to skin; nobody wants it.\n\nShe wipes the bar. The wood is already clean.'
  assert.deepEqual([...reworded(draft, saved)], ['The wood is already clean.'])
  assert.equal(reworded(saved, saved).size, 0)
})

const BANDS = [{ band: 'failure', label: 'Fail', ceiling: 30 }, { band: 'failure_upside', label: 'Fail with an upside', ceiling: 50 },
  { band: 'success_cost', label: 'Success at a cost', ceiling: 70 }, { band: 'success', label: 'Success', ceiling: 89 },
  { band: 'critical_success', label: 'Critical success', ceiling: null }] as const
const ROLL = { action: 'win her over', stat: 'Allure', difficulty: 'hard', die: 10, natural: 52, bonus: 7, shift: 10, total: 49, band: 'failure_upside', label: 'Fail with an upside' } as const

test('turnAfter builds a turn from its stream events in order', () => {
  let turn = turnAfter(NO_TURN, { stage: 'reading' })
  turn = turnAfter(turn, { actions: [{ action: 'win her over', stat: 'Allure', difficulty: 'hard' }], bands: [...BANDS] })
  turn = turnAfter(turn, { roll: { ...ROLL } })
  turn = turnAfter(turn, { stage: 'writing' })
  assert.equal(turn.stage, 'writing')
  assert.equal(turn.bands?.length, 5)
  assert.deepEqual(turn.rolls, [ROLL])
  assert.equal(turnAfter(NO_TURN, { actions: [{ action: 'a', stat: 'Luck' }] }).bands, null)
})

test('actionLine names the difficulty only while the dice are shown', () => {
  assert.equal(actionLine({ action: 'a', stat: 'Allure', difficulty: 'very_hard' }), 'Rolling Allure, very hard')
  assert.equal(actionLine({ action: 'a', stat: 'Allure' }), 'Testing your Allure')
})

test('bandSpans and markerAt lay the bands and a total on a 1 to 100 strip', () => {
  assert.deepEqual(bandSpans([...BANDS]).map(({ from, to }) => [from, to]), [[1, 30], [31, 50], [51, 70], [71, 89], [90, 100]])
  assert.equal(markerAt(124), 100)
  assert.equal(markerAt(-3), 1)
})

test('nearMiss says how close the next band was, within 5', () => {
  assert.equal(nearMiss({ ...ROLL }, [...BANDS]), '2 short of success at a cost')
  assert.equal(nearMiss({ ...ROLL, total: 40 }, [...BANDS]), '')
  assert.equal(nearMiss({ ...ROLL, total: 95, band: 'critical_success' }, [...BANDS]), '')
  assert.equal(nearMiss({ ...ROLL, total: 49, band: 'critical_failure', natural: 8 }, [...BANDS]), '')
})

test('the dice land on the roll the code made', () => {
  const roll = { action: 'Win her over', stat: 'Allure', difficulty: 'hard', die: 8, natural: 47, bonus: 5, shift: 10, total: 42, band: 'failure_upside' as const, label: 'Fail with an upside' }
  assert.deepEqual(diceFaces(roll).map((face) => face.value), ['40', '7', '5'])
  assert.deepEqual(diceFaces({ ...roll, natural: 100 }).slice(0, 2).map((face) => face.value), ['00', '0'])
  assert.deepEqual(diceFaces({ ...roll, natural: 5, die: null }).map((face) => face.value), ['00', '5'])
})

test('a tumbling die only shows faces it has', () => {
  const [tens, ones, stat] = diceFaces({ action: 'a', stat: 'Allure', difficulty: 'normal', die: 6, natural: 50, bonus: 1, shift: 0, total: 51, band: 'success_cost' as const, label: 'x' })
  assert.equal(tumbleFace(tens, 0.99), '90')
  assert.equal(tumbleFace(ones, 0), '0')
  assert.equal(tumbleFace(stat, 0), '1')
  assert.equal(tumbleFace(stat, 0.99), '6')
})

test('the 3D dice are told the faces to land on', () => {
  const roll = { action: 'a', stat: 'Allure', difficulty: 'normal', die: 8, natural: 52, bonus: 7, shift: 0, total: 59, band: 'success_cost' as const, label: 'x' }
  assert.equal(diceNotation(diceFaces(roll)), '1d100+1d10+1d8@50,2,7')
  assert.equal(diceNotation(diceFaces({ ...roll, natural: 100, die: null })), '1d100+1d10@100,10')
  assert.equal(diceNotation(diceFaces({ ...roll, natural: 7, die: null })), '1d100+1d10@100,7')
})

test('a 5E roll reads as a d20 and a bonus against the DC, and lands one d20', () => {
  const roll = { action: 'climb', stat: 'Vitality', difficulty: 'normal', die: 20, natural: 12, bonus: 5, shift: 0, total: 17, band: 'success' as const, label: 'Success', ruleset: 'srd52' as const, target: 15, skill: 'Athletics' }
  assert.equal(rollText(roll), 'Athletics d20: 12 + 5 = 17 vs DC 15, Success')
  assert.equal(rollText({ ...roll, bonus: -1, total: 11, band: 'failure', label: 'Fail' }), 'Athletics d20: 12 - 1 = 11 vs DC 15, Fail')
  assert.equal(rollWhat(roll), 'Athletics · DC 15')
  assert.deepEqual(diceFaces(roll), [{ key: 'd20', sides: 20, value: '12' }])
  assert.equal(diceNotation(diceFaces(roll)), '1d20@12')
})

test('a 5E ability reads as its score, modifier and save', () => {
  assert.equal(abilityLine('dex', 17, 3, true), 'Dex 17 (+3), save')
  assert.equal(abilityLine('cha', 8, -1, false), 'Cha 8 (-1)')
  assert.equal(signed(0), '+0')
})

test('a 5E build places the standard array once and picks only the skills left', () => {
  const array = [15, 14, 13, 12, 10, 8]
  assert.ok(arrayPlaced({ str: 15, dex: 14, con: 13, int: 12, wis: 10, cha: 8 }, array))
  assert.ok(!arrayPlaced({ str: 15, dex: 15, con: 13, int: 12, wis: 10, cha: 8 }, array))
  assert.deepEqual(skillChoices(['Athletics', 'Perception', 'Survival'], ['Athletics', 'Intimidation']), ['Perception', 'Survival'])
  assert.equal(skillId('Sleight of Hand'), 'sleight-of-hand')
})

test('xpLine and spellLine read a 5E character\'s level and spells', () => {
  assert.equal(xpLine(2, 325, 900), 'Level 2 · 325 XP, 900 for level 3')
  assert.equal(xpLine(20, 400000, null), 'Level 20 · 400000 XP, the highest level')
  assert.equal(spellLine({ ability: 'Intelligence', attack: 5, dc: 13, cantrips: [], prepared: [], slots: [{ level: 1, left: 1, of: 2 }, { level: 2, left: 3, of: 3 }] }),
    'Intelligence: spell attack +5 · save DC 13 · slots: 1st 1 of 2, 2nd 3 of 3')
})

test('an Ironsworn roll reads its move and lands an action die and two challenge dice', () => {
  const roll = { action: 'I climb', stat: 'Vitality', difficulty: 'normal', die: 6, natural: 4, bonus: 3, shift: 0, total: 7, band: 'success', label: 'Success', ruleset: 'ironsworn', target: null, skill: 'Face Danger +iron vs 5 and 6' } as const
  assert.equal(rollWhat(roll), 'Face Danger +iron')
  assert.equal(rollText(roll), 'Face Danger +iron vs 5 and 6: 4 + 3 = 7, Success')
  assert.deepEqual(challengeDice(roll.skill), [5, 6])
  assert.deepEqual(diceFaces(roll).map((face) => [face.sides, face.value]), [[6, '4'], [10, '5'], [10, '6']])
})

test('a turn receipt shows under the narration that answers its line', () => {
  const base = { seq: 1, text: '', status: 'complete' as const, error: null, city_id: 'kingswood', place_id: 'inn', created_at: '' }
  const chip = { kind: 'coins' as const, tone: 'gain' as const, text: '+2.50 cr.' }
  const receipts = receiptsByReply([
    { ...base, id: 'u1', role: 'user', reply_to: null, receipt: [chip] },
    { ...base, id: 'n1', role: 'narrator', reply_to: 'u1' },
    { ...base, id: 'u2', role: 'user', reply_to: null },
    { ...base, id: 'n2', role: 'narrator', reply_to: 'u2' },
  ])
  assert.deepEqual([...receipts.keys()], ['n1'])
  assert.deepEqual(receipts.get('n1'), [chip])
})

test('a Percentile roll reads its skill and chance and lands two percentile dice', () => {
  const roll = { action: 'I climb', stat: 'Vitality', difficulty: 'normal', die: 100, natural: 42, bonus: 0, shift: 0, total: 42, band: 'success', label: 'Success', ruleset: 'brp', target: 75, skill: 'Climb 75%' } as const
  assert.equal(rollWhat(roll), 'Climb 75%')
  assert.equal(rollText(roll), 'Climb 75% d100: 42 against 75, Success')
  assert.deepEqual(diceFaces(roll).map((face) => [face.sides, face.value]), [[10, '40'], [10, '2']])
})

test('Percentile characteristics cost a point each, DEX, INT and POW three', () => {
  assert.equal(brpCost({ str: 15, con: 14, siz: 13, int: 10, pow: 10, dex: 14, cha: 10 }, 10, ['dex', 'int', 'pow'], 3), 24)
  assert.equal(brpCost({ str: 8, dex: 12 }, 10, ['dex', 'int', 'pow'], 3), 4)
})

test('a spell with no slot left just fails, with no dice', () => {
  const roll = { action: 'I cast Ice Knife', stat: 'Essence', difficulty: 'normal', die: 20, natural: 0, bonus: 5, shift: 0, total: 0, band: 'failure', label: 'Failure', ruleset: 'srd52', target: 12, skill: 'Ice Knife (no spell slot left)' } as const
  assert.ok(unrolled(roll))
  assert.equal(rollText(roll), 'Ice Knife (no spell slot left): no roll, Failure')
  assert.ok(!unrolled({ ...roll, natural: 7 }))
})

test('a school says its term, grades and what is on today', () => {
  const grades = { average: 85, letter: 'B', gpa: 3, attended: 5, missed: 1 }
  assert.equal(institutionLine({ term: 'Fall term 2009', grades }), 'Fall term 2009 · B (3.0) · 1 class missed')
  assert.equal(institutionLine({ term: 'Fall term 2009', grades: null }), 'Fall term 2009 · no grades yet')
  assert.equal(institutionLine({ term: null, grades: null }), 'Out of term')
  const today = [{ id: 'letters', name: 'Letters', at: '10:00', place_id: null, soon: true }]
  assert.equal(todayLine({ term: 'Fall term 2009', today }), 'Today: Letters at 10:00')
  assert.equal(todayLine({ term: 'Fall term 2009', today: [] }), 'No more classes today')
  assert.equal(questState({ status: 'open', left: '2 days left', kind: 'coursework' }), 'Coursework · Underway · 2 days left')
})

test('a picture says what it shows and where it stands', () => {
  const people = [{ key: 'town:k:0', name: 'Fenwick Cutter' }]
  assert.equal(artLabel({ kind: 'portrait', subject: 'player' }, people), 'You')
  assert.equal(artLabel({ kind: 'portrait', subject: 'town:k:0' }, people), 'Fenwick Cutter')
  assert.equal(artLabel({ kind: 'place', subject: 'kingswood/pell-provisions' }, people), 'Pell provisions')
  assert.equal(artLabel({ kind: 'scene', subject: 'kingswood/pell-provisions' }, people, 'Pell Provisions'), 'The scene at Pell Provisions')
  assert.equal(artStatus({ status: 'running', error: null, stale: false }), 'Making it…')
  assert.equal(artStatus({ status: 'refused', error: 'No image backend is enabled.', stale: false }), 'No image backend is enabled.')
  assert.equal(artStatus({ status: 'done', error: null, stale: true }), 'Out of date: something has changed since.')
  assert.equal(making([{ status: 'done' }, { status: 'queued' }]), true)
})

test('a veil toggles in and out in the list order', () => {
  assert.deepEqual(toggledVeil(['self-harm'], 'torture', true), ['torture', 'self-harm'])
  assert.deepEqual(toggledVeil(['torture', 'self-harm'], 'torture', false), ['self-harm'])
})

test('a portrait can be asked of someone here before they are met, and of anyone met', () => {
  assert.deepEqual(pictureChoices([{ key: 'a', name: 'Ada' }, { key: 'b', name: 'Bo' }], [{ key: 'b', label: 'Bo, the barkeep' }, { key: 'c', label: 'the smith' }]),
    [{ key: 'b', label: 'Bo, the barkeep (here)' }, { key: 'c', label: 'the smith (here)' }, { key: 'a', label: 'Ada' }])
})

test('a Fate roll shows its four faces, its line and where it lands on the ladder', () => {
  const roll = { action: 'slip away', stat: 'Mind', difficulty: 'normal', die: 0, natural: 1, bonus: 5, shift: 0, total: 6, band: 'critical_success' as const,
    label: 'Critical success', ruleset: 'fate' as const, target: 2, skill: 'Sneaky +3 vs Fair (+2) (stunt +2), dice +0−+' }
  assert.deepEqual(fateFaces(roll.skill), ['+', '0', '−', '+'])
  assert.deepEqual(diceFaces(roll).map((face) => face.key), ['fate1', 'fate2', 'fate3', 'fate4'])
  assert.equal(rollWhat(roll), 'Sneaky +3 vs Fair (+2) (stunt +2)')
  assert.equal(rollText(roll), 'Sneaky +3 vs Fair (+2) (stunt +2): +1 + 5 = Fantastic (+6), Critical success')
  assert.equal(fateLadder(-5), 'Terrible')
  assert.ok(['−', '0', '+'].includes(tumbleFace(diceFaces(roll)[0], 0.5)))
})

test('otherTowns offers only this world\'s towns off the travel map, never a road between towns', () => {
  const cities = [
    { id: 'kingswood', name: 'Kingswood', world: 'vallarith' }, { id: 'hollin', name: 'Hollin', world: 'vallarith' },
    { id: 'vallarith-road', name: 'the Road', world: 'vallarith', home: false }, { id: 'eriane', name: 'Eriane', world: 'vallarith' },
    { id: 'haven', name: 'Haven', world: 'havenbrooke' }, { id: 'haddon', name: 'Haddon Harbor', world: null },
  ]
  assert.deepEqual(otherTowns(cities, 'kingswood', ['Hollin']).map((city) => city.id), ['eriane'])
  assert.deepEqual(otherTowns(cities, 'haddon', []).map((city) => city.id), [])
  assert.deepEqual(otherTowns(cities, 'nowhere', []), [])
})
