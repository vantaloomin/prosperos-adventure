// The round loop as the play screen sees it (adventure/round_routes.py, adventure/rounds/contract.py). Kept free of
// React and of imports with side effects, so tests/ui can load it directly.

export type RoundState = 'idle' | 'gathering' | 'declaring' | 'reacting' | 'conversing' | 'awaiting_user' | 'resolving'
  | 'writing' | 'committing' | 'committed' | 'discarded'
export type Mind = 'agent' | 'program' | 'human'
export type Mode = 'play' | 'author' | 'watch'
export type SeatStatus = 'thinking' | 'declared' | 'reacting' | 'done' | 'fallback'

/** A character at the table: an agent, a Program mind (Dungeon's code minds) or the human (adventure/rounds/seats.py). */
export interface Seat {
  key: string; name: string; mind: Mind; order: number; model_profile_id: string | null; notes: string; promoted: boolean
}
/** The reply card: `speaker` addressed the human at `seat` (adventure/rounds/reply.py). */
export interface Awaiting { seat: string; speaker: string; line: string; context: string[] }
export interface RoundTurn {
  id: string; state: RoundState; mode: Mode; marks: unknown[]; reask_of: string | null; reask_seat: string | null
  error: string | null; awaiting: Awaiting | null
}
export interface RoundSettings { mode: Mode; agent_cap: number; converse_cap: number; queued: Partial<Omit<RoundSettings, 'queued'>> }
/** GET /api/rounds: the table as it stands. `head` is the newest turn, which every turn command is sent against. */
export interface RoundTable { settings: RoundSettings; seats: Seat[]; under_way: RoundTurn | null; head: string | null }

/** What the stream has said about the turn under way: its state, each character's row, and the reply card. */
export interface RoundLive {
  turnId: string | null; state: RoundState | null
  seats: Record<string, { status: SeatStatus; intent?: string }>
  awaiting: Awaiting | null
}

export const NO_ROUND: RoundLive = { turnId: null, state: null, seats: {}, awaiting: null }

type RoundEvent = { round: { turn_id: string; state: RoundState } } | { seat: { key: string; status: SeatStatus; intent?: string } }
  | { awaiting: Awaiting }

/** A turn under way with one more of its stream events; the story's own events (stage, actions, roll) pass by. */
export function roundAfter(live: RoundLive, event: unknown): RoundLive {
  if (!event || typeof event !== 'object') return live
  const known = event as RoundEvent
  if ('round' in known) return stateAfter(live, known.round.turn_id, known.round.state)
  if ('seat' in known) return seatAfter(live, known.seat)
  if ('awaiting' in known) return { ...live, awaiting: known.awaiting }
  return live
}

/** A new turn starts with no rows; the reply card stays only while the same turn still waits. */
function stateAfter(live: RoundLive, turnId: string, state: RoundState): RoundLive {
  const same = turnId === live.turnId
  return { turnId, state, seats: same ? live.seats : {}, awaiting: same && state === 'awaiting_user' ? live.awaiting : null }
}

function seatAfter(live: RoundLive, seat: { key: string; status: SeatStatus; intent?: string }): RoundLive {
  const intent = seat.intent ?? live.seats[seat.key]?.intent
  return { ...live, seats: { ...live.seats, [seat.key]: { status: seat.status, ...(intent ? { intent } : {}) } } }
}

/** A stream starting: an answer to the reply card goes on with the same turn and keeps its rows; anything else starts
 *  afresh. */
export function roundStarting(live: RoundLive): RoundLive {
  return live.state === 'awaiting_user' ? { ...live, awaiting: null } : NO_ROUND
}

/** The round timeline's steps (docs/spec.md "Waiting and pauses"), each lit by the states it covers. */
export const STEPS: { name: string; states: RoundState[] }[] = [
  { name: 'Declare', states: ['gathering', 'declaring'] },
  { name: 'React', states: ['reacting'] },
  { name: 'Converse', states: ['conversing', 'awaiting_user'] },
  { name: 'Resolve', states: ['resolving'] },
  { name: 'Write', states: ['writing', 'committing'] },
]

/** Which step is lit: -1 before a turn or after it. */
export function stepAt(state: RoundState | null): number {
  return state ? STEPS.findIndex((step) => step.states.includes(state)) : -1
}

/** Whether a turn is under way, from the stream or, on opening the page, from the table. */
export function underWay(live: RoundLive, table?: RoundTable | null): boolean {
  if (live.state) return !['idle', 'committed', 'discarded'].includes(live.state)
  return !!table?.under_way
}

/** The reply card on screen: the stream's, or the one a turn was left waiting on (after a reload or a restart). */
export function waitingOn(live: RoundLive, table?: RoundTable | null): { turnId: string; awaiting: Awaiting } | null {
  if (live.awaiting && live.turnId && live.state === 'awaiting_user') return { turnId: live.turnId, awaiting: live.awaiting }
  if (live.state && live.state !== 'awaiting_user') return null
  const open = table?.under_way
  return open?.state === 'awaiting_user' && open.awaiting ? { turnId: open.id, awaiting: open.awaiting } : null
}

/** Whether anyone at the table thinks for themselves; with nobody, the play screen is exactly Dungeon's. */
export const hasAgents = (table?: RoundTable | null) => !!table?.seats.some((seat) => seat.mind === 'agent')

export const seatOf = (table: RoundTable | null | undefined, key: string) => table?.seats.find((seat) => seat.key === key)

/** A seat's name, or the key it was given when it has no seat. */
export const seatName = (table: RoundTable | null | undefined, key: string) => seatOf(table, key)?.name ?? key

/** A character's row during a turn. In Play only that they decided ("Decided"), never what; in Author and Watch, their
 *  intent once it arrives. The one who spoke to the user's character waits for the answer. */
export function seatLine(key: string, live: RoundLive, mode: Mode, waiting: Awaiting | null): string | null {
  if (waiting?.speaker === key) return 'Waiting for your answer'
  const row = live.seats[key]
  if (!row) return null
  if (row.status === 'thinking') return 'Thinking'
  if (row.status === 'reacting') return 'Reacting'
  if (row.status === 'fallback') return 'Went by the rules this turn'
  return mode !== 'play' && row.intent ? row.intent : 'Decided'
}

/** The polite live region's summary: "3 of 5 characters have decided", or who is waiting for an answer. */
export function liveSummary(live: RoundLive, table: RoundTable | null | undefined, waiting: Awaiting | null): string {
  if (waiting) return `${seatName(table, waiting.speaker)} is waiting for your answer`
  const rows = Object.values(live.seats)
  if (!rows.length) return ''
  const decided = rows.filter((row) => row.status !== 'thinking').length
  return `${decided} of ${rows.length} ${rows.length === 1 ? 'character has' : 'characters have'} decided`
}

/** The round loop as the cast list shows it: the turn under way, the table's seats, the reply card if one is up, and
 *  the Thinks or Rules choice for a character. */
export interface CastRound {
  live: RoundLive; table?: RoundTable; waiting: Awaiting | null
  onMind: (person: { key: string; name: string }, mind: 'agent' | 'program') => void
}

/** The mode a row is read in: the turn's own while one is under way, else the campaign's. */
export const modeOf = (table?: RoundTable | null): Mode => table?.under_way?.mode ?? table?.settings.mode ?? 'play'

export type ReplyKind = 'reply' | 'silent' | 'let_answer'

/** The reply card's answer, as POST /api/rounds/turns/{id}/reply/stream takes it. */
export function replyBody(waiting: Awaiting, kind: ReplyKind, text: string, against: string | null) {
  return { seat: waiting.seat, kind, text: kind === 'reply' ? text.trim() : '', against }
}

/** The seats to write when a character is made to think or to go by the rules: theirs, and the user's own seat as the
 *  human when the table has none yet, so an agent can speak to them and the reply card can come up. */
export function seatChanges(table: RoundTable | null | undefined, person: { key: string; name: string }, mind: 'agent' | 'program',
  you: { key: string; name: string }): { key: string; body: { name: string; mind: Mind } }[] {
  const changes = [{ key: person.key, body: { name: person.name, mind: mind as Mind } }]
  const human = table?.seats.some((seat) => seat.mind === 'human')
  return mind === 'agent' && !human ? [{ key: you.key, body: { name: you.name, mind: 'human' } }, ...changes] : changes
}

/** The page title while a character waits on the user's answer, so a tab in the background shows it. */
export function titleWhile(waiting: boolean, title: string): string {
  const plain = title.replace(/^\(1\) /, '')
  return waiting ? `(1) ${plain}` : plain
}
