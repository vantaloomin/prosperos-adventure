import assert from 'node:assert/strict'
import { test } from 'node:test'
import { asksMissed, beatMoves, beatStanding, decidedCount, itemText, hasAgents, modeChosen, modeOf, motivesOf, openingKind, watchNext, watchOf, WATCH_SECONDS, NO_ROUND, replyBody, roundAfter, roundStarting, rowStatus, seatChanges, stepAt, STEPS, underWay, waitingOn, type RoundLive, type RoundTable, type Seat } from '../../src/features/round/round.ts'
import { composerText, pauseLine, secondsName, mindLines, checksLine, rollLine, turnName, estimateLine, liveSummary, replyText, rowText, spendLine, STEP_NAMES, stepLine, titleWhile } from '../../src/features/round/roundText.ts'

const seat = (key: string, mind: Seat['mind']): Seat => ({ key, name: key.charAt(0).toUpperCase() + key.slice(1), mind, order: 0, model_profile_id: null, notes: '', promoted: false })
const table = (seats: Seat[], under_way: RoundTable['under_way'] = null): RoundTable => ({
  settings: { mode: 'play', agent_cap: 6, converse_cap: 4, queued: {} }, seats, under_way, head: under_way?.id ?? null,
})
const card = { seat: 'you', speaker: 'mara', line: 'Where were you last night?', context: ['Mara leans in.'] }
const heard = (...events: unknown[]) => events.reduce<RoundLive>((live, event) => roundAfter(live, event), NO_ROUND)

test('the stream builds the turn: its state, each row, and the reply card', () => {
  const live = heard({ round: { turn_id: 't1', state: 'declaring' } }, { seat: { key: 'hesk', status: 'thinking' } },
    { seat: { key: 'mara', status: 'thinking' } }, { seat: { key: 'hesk', status: 'declared', intent: 'slips out the back' } },
    { stage: 'reading' }, { round: { turn_id: 't1', state: 'awaiting_user' } }, { awaiting: card })
  assert.equal(live.state, 'awaiting_user')
  assert.deepEqual(live.seats, { hesk: { status: 'declared', intent: 'slips out the back' }, mara: { status: 'thinking' } })
  assert.deepEqual(live.awaiting, card)
  // A later status keeps the intent already shown.
  assert.deepEqual(roundAfter(live, { seat: { key: 'hesk', status: 'done' } }).seats.hesk, { status: 'done', intent: 'slips out the back' })
  // Going on from the card puts it away; a new turn starts with no rows.
  assert.equal(roundAfter(live, { round: { turn_id: 't1', state: 'resolving' } }).awaiting, null)
  assert.deepEqual(roundAfter(live, { round: { turn_id: 't2', state: 'gathering' } }), { turnId: 't2', state: 'gathering', seats: {}, awaiting: null })
})

test('a stream answering the card keeps the turn; any other starts afresh', () => {
  const waiting = heard({ round: { turn_id: 't1', state: 'awaiting_user' } }, { seat: { key: 'mara', status: 'declared' } }, { awaiting: card })
  assert.deepEqual(roundStarting(waiting), { ...waiting, awaiting: null })
  assert.equal(roundStarting(heard({ round: { turn_id: 't1', state: 'idle' } })), NO_ROUND)
})

test('the timeline lights one step at a time', () => {
  assert.deepEqual(STEPS.map((step) => STEP_NAMES[step.key]), ['Declare', 'React', 'Talk', 'Roll', 'Write'])
  assert.equal(stepAt(null), -1)
  assert.equal(stepAt('gathering'), 0)
  assert.equal(stepAt('awaiting_user'), 2)
  assert.equal(stepAt('committing'), 4)
  assert.equal(stepAt('idle'), -1)
  const live = heard({ round: { turn_id: 't1', state: 'declaring' } }, { seat: { key: 'hesk', status: 'declared' } }, { seat: { key: 'mara', status: 'thinking' } }, { seat: { key: 'bren', status: 'fallback' } })
  assert.equal(stepLine('declaring', live), 'Declaring · 2 of 3')
  assert.equal(stepLine('awaiting_user', live), 'Waiting for you')
  assert.equal(stepLine('resolving', live), 'Rolling')
  assert.equal(stepLine('idle', live), '')
  assert.deepEqual(decidedCount(live), { decided: 2, of: 3 })
})

test('the reply card comes from the stream, or from the table after a reload', () => {
  const open = { id: 't9', state: 'awaiting_user' as const, mode: 'play' as const, marks: [], reask_of: null, reask_seat: null, error: null, awaiting: card }
  assert.deepEqual(waitingOn(NO_ROUND, table([], open)), { turnId: 't9', awaiting: card })
  assert.equal(waitingOn(NO_ROUND, table([])), null)
  const live = heard({ round: { turn_id: 't1', state: 'awaiting_user' } }, { awaiting: card })
  assert.deepEqual(waitingOn(live, null), { turnId: 't1', awaiting: card })
  // Once the stream has moved on, an old table does not bring the card back.
  assert.equal(waitingOn(heard({ round: { turn_id: 't9', state: 'conversing' } }), table([], open)), null)
  assert.equal(underWay(NO_ROUND, table([], open)), true)
  assert.equal(underWay(heard({ round: { turn_id: 't9', state: 'idle' } }), table([], open)), false)
})

test('a row says only that a character decided in Play, and what they mean to do in Author and Watch', () => {
  const live = heard({ round: { turn_id: 't1', state: 'reacting' } }, { seat: { key: 'hesk', status: 'declared', intent: 'slips out the back' } },
    { seat: { key: 'ilsa', status: 'reacting' } }, { seat: { key: 'bren', status: 'fallback' } }, { seat: { key: 'mara', status: 'thinking' } })
  assert.equal(rowText('hesk', live, 'play', null), 'Decided')
  assert.equal(rowText('hesk', live, 'watch', null), 'slips out the back')
  assert.equal(rowText('ilsa', live, 'play', null), 'Thinking')
  assert.equal(rowText('bren', live, 'play', null), 'Went by the rules')
  assert.equal(rowText('mara', live, 'play', null), 'Thinking')
  assert.equal(rowText('mara', live, 'play', card), 'Waiting for you')
  assert.equal(rowText('nobody', live, 'play', null), null)
  assert.equal(rowStatus('ilsa', live, null), 'thinking')
  assert.equal(rowStatus('mara', live, card), 'waiting')
  assert.equal(rowStatus('hesk', live, null), 'decided')
})

test('the live region sums the turn up', () => {
  const seats = table([seat('mara', 'agent'), seat('hesk', 'agent')])
  assert.equal(liveSummary(NO_ROUND, seats, null), '')
  const live = heard({ round: { turn_id: 't1', state: 'declaring' } }, { seat: { key: 'hesk', status: 'declared' } }, { seat: { key: 'mara', status: 'thinking' } })
  assert.equal(liveSummary(live, seats, null), '1 of 2 characters have decided')
  assert.equal(liveSummary(heard({ seat: { key: 'hesk', status: 'thinking' } }), seats, null), '0 of 1 character has decided')
  assert.equal(liveSummary(live, seats, card), 'Mara is waiting for you')
})

test('making a character think seats the user too, once', () => {
  const you = { key: 'you', name: 'Ada' }
  assert.deepEqual(seatChanges(table([]), { key: 'mara', name: 'Mara' }, 'agent', you), [
    { key: 'you', body: { name: 'Ada', mind: 'human' } }, { key: 'mara', body: { name: 'Mara', mind: 'agent' } }])
  assert.deepEqual(seatChanges(table([seat('you', 'human')]), { key: 'mara', name: 'Mara' }, 'agent', you), [{ key: 'mara', body: { name: 'Mara', mind: 'agent' } }])
  assert.deepEqual(seatChanges(table([]), { key: 'mara', name: 'Mara' }, 'program', you), [{ key: 'mara', body: { name: 'Mara', mind: 'program' } }])
})

test('the table, the reply and the title', () => {
  assert.equal(hasAgents(table([seat('you', 'human'), seat('mara', 'program')])), false)
  assert.equal(hasAgents(table([seat('mara', 'agent')])), true)
  assert.equal(modeOf(null), 'play')
  assert.deepEqual(replyBody(card, 'reply', '  At the shrine. ', 't1'), { seat: 'you', kind: 'reply', text: 'At the shrine.', against: 't1' })
  assert.deepEqual(replyBody(card, 'silent', 'ignored', 't1'), { seat: 'you', kind: 'silent', text: '', against: 't1' })
  assert.equal(replyText('Ada').letAnswer, 'Let Ada answer')
  assert.equal(replyText('').letAnswer, 'Let your character answer')
  assert.equal(titleWhile(true, 'Adventure'), '(1) Adventure')
  assert.equal(titleWhile(true, '(1) Adventure'), '(1) Adventure')
  assert.equal(titleWhile(false, '(1) Adventure'), 'Adventure')
})

test('the pace reads plainly', () => {
  assert.equal(estimateLine({ calls: 14, tokens: 9400 }), '~14 calls · 9k tokens')
  assert.equal(estimateLine({ calls: 1, tokens: 600 }), '~1 call · 600 tokens')
  assert.equal(estimateLine({ calls: 14, tokens: 9400, seconds: 43.4 }), '~43 s · 14 calls')
  assert.equal(spendLine({ spent: 12400, held: 0, cap: 200000 }), '12k of 200k tokens this session')
  assert.equal(spendLine({ spent: 0, held: 0, cap: 0 }), '0 tokens this session')
})

test('the turn report reads plainly', () => {
  assert.equal(turnName(12), 'Turn 12')
  const names = (key: string) => ({ hesk: 'Hesk' })[key] ?? key
  assert.equal(rollLine({ actor: 'hesk', action: 'picks the lock', stat: 'Deft', result: 'success' }, names), 'Hesk · picks the lock · Deft · success')
  assert.equal(rollLine({ actor: 'hesk', action: 'picks the lock', stat: 'Deft', result: 'success', total: 16 }, names), 'Hesk · picks the lock · Deft · success, 16')
  assert.equal(checksLine({ scan: {}, cut: [], rewrites: 0, review: [] }), '')
  assert.equal(checksLine({ scan: {}, cut: ['A line.'], rewrites: 2, review: [{ quote: 'q', problem: 'p', fix: 'f' }] }), '2 rewrites · 1 sentence cut · 1 note')
  assert.equal(itemText('The bridge burns'), 'The bridge burns')
  assert.equal(itemText({ who: 'tobin', text: 'Tobin sold the map' }), 'Tobin sold the map')
  assert.equal(itemText({ who: 'tobin' }), '')
})

test('the GM view reads each mind in full', () => {
  const names = (key: string) => ({ you: 'Ada', hesk: 'Hesk' })[key] ?? key
  assert.deepEqual(mindLines({ key: 'mara', name: 'Mara', mind: 'agent', status: 'decided', intent: 'asks where Ada was', motive: 'thinks Ada sold her out',
    lines: [{ text: 'Where were you?', to: ['you'] }], whispers: [{ text: 'Watch her hands', to: 'hesk' }] }, names),
  ['asks where Ada was', '“Where were you?” to Ada', 'whispers “Watch her hands” to Hesk'])
  assert.deepEqual(mindLines({ key: 'bren', name: 'Bren', mind: 'program', status: 'waiting' }, names), [])
})

test('the switcher shows the mode chosen, even while it waits for the turn to end', () => {
  assert.equal(modeChosen(null), 'play')
  const waiting = { ...table([seat('mara', 'agent')]), settings: { mode: 'play' as const, agent_cap: 6, converse_cap: 4, queued: { mode: 'watch' as const } } }
  assert.equal(modeChosen(waiting), 'watch')
  assert.equal(modeChosen(table([])), 'play')
})

test('Watch plays on until paused, and says why when it stops by itself', () => {
  const idle = { playing: true, busy: false, waiting: false, paused: null, error: '' }
  assert.deepEqual(watchNext(idle), { go: true, pause: null })
  assert.deepEqual(watchNext({ ...idle, playing: false }), { go: false, pause: null })
  assert.deepEqual(watchNext({ ...idle, busy: true }), { go: false, pause: null })
  assert.deepEqual(watchNext({ ...idle, waiting: true }), { go: false, pause: null })
  const betrayed = { kind: 'betrayal', text: 'Mara betrayed the party.', turn_id: 't4' }
  assert.deepEqual(watchNext({ ...idle, paused: betrayed }), { go: false, pause: betrayed })
  assert.deepEqual(watchNext({ ...idle, playing: false, paused: betrayed }).pause, betrayed)
  assert.deepEqual(watchNext({ ...idle, error: 'The model timed out.' }), { go: false, pause: { kind: 'error', text: 'The model timed out.' } })
  assert.equal(pauseLine(betrayed), 'Paused: Mara betrayed the party')
  assert.equal(pauseLine({ kind: 'cap', text: 'This session reached its cap.' }), 'Paused: This session reached its cap')
  assert.equal(pauseLine({ kind: 'error', text: 'Paused: Mara died.' }), 'Paused: Mara died')
  assert.deepEqual(watchOf(false, { seconds: 20, paused: betrayed }), { seconds: 20, paused: null })
  assert.deepEqual(watchOf(true, undefined), { seconds: 0, paused: null })
  assert.deepEqual(WATCH_SECONDS.map(secondsName), ['By hand', '10 s', '20 s', '40 s', '1 min'])
})

test('a turn opens on the player\'s line, the author\'s nudge, or nothing', () => {
  assert.equal(openingKind({ role: 'user', text: 'I knock.', mode: 'play' }), 'line')
  assert.equal(openingKind({ role: 'user', text: 'I knock.' }), 'line')
  assert.equal(openingKind({ role: 'user', text: 'The storm comes early', mode: 'author' }), 'nudge')
  assert.equal(openingKind({ role: 'user', text: '', mode: 'watch' }), 'none')
  assert.equal(openingKind({ role: 'narrator', text: '' }), 'line')
  assert.equal(composerText(false, true).placeholder, 'What do you do or say?')
  assert.deepEqual([composerText(true, true).placeholder, composerText(true, true).send, composerText(true, false).send], ['Nudge the story', 'Next', 'Send'])
})

test('the open row shows a motive only where the minds panel gave one', () => {
  assert.deepEqual(motivesOf(undefined), {})
  assert.deepEqual(motivesOf([{ key: 'mara', name: 'Mara', mind: 'agent', status: 'decided', motive: 'thinks Ada sold her out' },
    { key: 'hesk', name: 'Hesk', mind: 'agent', status: 'decided' }]), { mara: 'thinks Ada sold her out' })
})

test('leaving Play asks about missed motives once, and only from Play', () => {
  assert.equal(asksMissed('play', 'watch', null), true)
  assert.equal(asksMissed('play', 'author', false), false)
  assert.equal(asksMissed('play', 'author', undefined), false)
  assert.equal(asksMissed('author', 'watch', null), false)
  assert.equal(asksMissed('watch', 'play', null), false)
})

test('the beat board marks where a beat stands and which ways it can move', () => {
  const beat = { id: 'b1', text: 'A storm', cut: false, used: false, landed: false, source: 'director' }
  assert.equal(beatStanding(beat), null)
  assert.equal(beatStanding({ ...beat, used: true }), 'used')
  assert.equal(beatStanding({ ...beat, used: true, landed: true }), 'landed')
  assert.deepEqual(beatMoves(0, 3), { up: false, down: true })
  assert.deepEqual(beatMoves(2, 3), { up: true, down: false })
  assert.deepEqual(beatMoves(0, 1), { up: false, down: false })
})
