import assert from 'node:assert/strict'
import { test } from 'node:test'
import { estimateLine, spendLine, hasAgents, liveSummary, modeOf, NO_ROUND, replyBody, roundAfter, roundStarting, seatChanges, seatLine, stepAt, STEPS, titleWhile, underWay, waitingOn, type RoundLive, type RoundTable, type Seat } from '../../src/features/round/round.ts'

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
  assert.deepEqual(STEPS.map((step) => step.name), ['Declare', 'React', 'Converse', 'Resolve', 'Write'])
  assert.equal(stepAt(null), -1)
  assert.equal(stepAt('gathering'), 0)
  assert.equal(stepAt('awaiting_user'), 2)
  assert.equal(stepAt('committing'), 4)
  assert.equal(stepAt('idle'), -1)
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
  assert.equal(seatLine('hesk', live, 'play', null), 'Decided')
  assert.equal(seatLine('hesk', live, 'watch', null), 'slips out the back')
  assert.equal(seatLine('ilsa', live, 'play', null), 'Reacting')
  assert.equal(seatLine('bren', live, 'play', null), 'Went by the rules this turn')
  assert.equal(seatLine('mara', live, 'play', null), 'Thinking')
  assert.equal(seatLine('mara', live, 'play', card), 'Waiting for your answer')
  assert.equal(seatLine('nobody', live, 'play', null), null)
})

test('the live region sums the turn up', () => {
  const seats = table([seat('mara', 'agent'), seat('hesk', 'agent')])
  assert.equal(liveSummary(NO_ROUND, seats, null), '')
  const live = heard({ round: { turn_id: 't1', state: 'declaring' } }, { seat: { key: 'hesk', status: 'declared' } }, { seat: { key: 'mara', status: 'thinking' } })
  assert.equal(liveSummary(live, seats, null), '1 of 2 characters have decided')
  assert.equal(liveSummary(heard({ seat: { key: 'hesk', status: 'thinking' } }), seats, null), '0 of 1 character has decided')
  assert.equal(liveSummary(live, seats, card), 'Mara is waiting for your answer')
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
  assert.equal(titleWhile(true, 'Adventure'), '(1) Adventure')
  assert.equal(titleWhile(true, '(1) Adventure'), '(1) Adventure')
  assert.equal(titleWhile(false, '(1) Adventure'), 'Adventure')
})

test('the pace reads plainly', () => {
  assert.equal(estimateLine({ calls: 14, tokens: 9400 }), 'About 14 calls and 9k tokens a turn')
  assert.equal(estimateLine({ calls: 1, tokens: 600 }), 'About 1 call and 600 tokens a turn')
  assert.equal(spendLine({ spent: 12400, held: 0, cap: 200000 }), '12k of 200k tokens this session')
  assert.equal(spendLine({ spent: 0, held: 0, cap: 0 }), '0 tokens this session')
})
