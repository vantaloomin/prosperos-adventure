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

/** The round timeline's steps (docs/spec.md "The turn loop"), each lit by the states it covers; their names are in
 *  ./roundText.ts. */
export const STEPS: { key: 'declare' | 'react' | 'talk' | 'roll' | 'write'; states: RoundState[] }[] = [
  { key: 'declare', states: ['gathering', 'declaring'] },
  { key: 'react', states: ['reacting'] },
  { key: 'talk', states: ['conversing', 'awaiting_user'] },
  { key: 'roll', states: ['resolving'] },
  { key: 'write', states: ['writing', 'committing'] },
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

/** Where a character's row is this turn: thinking (declaring or reacting), decided, gone by the rules (an agent that
 *  failed ran on its Program mind), or waiting for the user's answer; null before they have a row. */
export type RowStatus = 'thinking' | 'decided' | 'fallback' | 'waiting'

export function rowStatus(key: string, live: RoundLive, waiting: Awaiting | null): RowStatus | null {
  if (waiting?.speaker === key) return 'waiting'
  const row = live.seats[key]
  if (!row) return null
  if (row.status === 'thinking' || row.status === 'reacting') return 'thinking'
  return row.status === 'fallback' ? 'fallback' : 'decided'
}

/** How many of the characters with a row have decided, of how many. */
export function decidedCount(live: RoundLive): { decided: number; of: number } {
  const rows = Object.values(live.seats)
  return { decided: rows.filter((row) => row.status !== 'thinking').length, of: rows.length }
}

/** The round loop as the cast list shows it: the turn under way, the table's seats, the reply card if one is up, and
 *  the Thinks or Rules choice for a character. */
export interface CastRound {
  live: RoundLive; table?: RoundTable; waiting: Awaiting | null
  /** Each character's motive on the watched turn, in Author and Watch only (GET /api/minds); shown in the open row. */
  motives: Record<string, string>
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

// Pace (adventure/agent_routes.py): the agents' preset with its estimate, the dials, and the session's spend. -----------

export type PresetKey = 'quick' | 'balanced' | 'rich'
export type Loyalty = 'slow' | 'steady' | 'fast'
export interface AgentPace {
  preset: PresetKey; scheming: number; loyalty: Loyalty; session_cap: number
  presets: { key: PresetKey; name: string; estimate: { calls: number; tokens: number; seconds?: number } }[]
  spend: { spent: number; held: number; cap: number }; capped: boolean
}

// The turn report and the status line (adventure/rounds/report.py). ------------------------------------------------

/** One of the report's free-form items (an invention, an off-page beat, a question): text, or an object carrying it. */
export type ReportItem = string | Record<string, unknown>
export interface ReportRoll { actor: string; action: string; stat: string; result: string; total?: number; difficulty?: number | string }
export interface TurnReport {
  turn_id: string; number: number; mode: Mode; state: RoundState; marks: unknown[]
  set: { intent: string; lines: string[]; beats: string[] }
  rolls: ReportRoll[]; numbers: string[]
  inventions: (Record<string, unknown> & { name?: string; struck?: boolean })[]
  corrections: { id: string; kind: string; target: string; before: unknown; after: unknown; why: string }[]
  checks: { scan: { words?: number; findings?: { kind: string; severity: string; text: string }[] }; cut: string[]; rewrites: number; review: { quote: string; problem: string; fix: string }[] }
  offpage: ReportItem[]; questions: ReportItem[]; motives: { seat: string; motive: string }[]; next: string
}
export interface StatusLine { last: { turn_id: string; number: number } | null; pending: { turn_id: string; state: RoundState; seat: string | null } | null; offpage_within: number }

/** The words of a free-form report item. */
export function itemText(item: ReportItem): string {
  if (typeof item === 'string') return item
  const found = ['text', 'line', 'outcome', 'name', 'question'].map((key) => item[key]).find((value) => typeof value === 'string' && value)
  return typeof found === 'string' ? found : ''
}

// The GM view of a round (adventure/gm.py open_round, adventure/rounds/context.py minds). --------------------------

export interface MindRow {
  key: string; name: string; mind: Mind; status: 'decided' | 'waiting' | 'fallback'
  intent?: string; motive?: string; lines?: { text: string; to: string[] | string | null }[]; whispers?: { text: string; to: string[] | string | null }[]
}
export interface GmRound { turn: { id: string; state: RoundState; mode: Mode; marks: unknown[] } | null; minds?: MindRow[]; marked: string[] }

/** The code the GM view answers with in Play until the user has said yes. */
export const ASKS_FIRST = 'gm_view_asks_first'

// Modes (docs/spec.md "Modes"): Play, Author and Watch, and Watch's own play and pause. ----------------------------

export const MODES: Mode[] = ['play', 'author', 'watch']

/** What a story line needs for its round tools: the table (for names) and the turns the GM view was open on. */
export interface LineMarks { table?: RoundTable; marked: string[] }

/** The mode the switcher shows: a change made while a turn is under way waits for Idle, and shows as made. */
export const modeChosen = (table?: RoundTable | null): Mode => table?.settings.queued.mode ?? table?.settings.mode ?? 'play'

/** Why Watch is paused (GET /api/rounds/watch `paused`): the session cap ('cap'), a big moment of the newest turn
 *  (death, betrayal, nemesis, chapter, or whatever a step flagged), or, on the screen only, a turn that failed
 *  ('error'). `turn_id` is the turn to go on from. */
export interface WatchPaused { kind: string; text: string; turn_id?: string | null }
export type WatchPause = WatchPaused | null
/** GET /api/rounds/watch: the timer between Watch turns in seconds (0 is by hand only), and why it is paused. */
export interface WatchState { seconds: number; paused: WatchPaused | null }

/** Whether Watch may start the next turn by itself now, and if not, why it pauses: the backend's reason first, then a
 *  turn that failed. Waiting on a reply card or a turn still being played holds without a banner. */
export function watchNext(state: { playing: boolean; busy: boolean; waiting: boolean; paused: WatchPause; error: string }):
  { go: boolean; pause: WatchPause } {
  if (state.paused) return { go: false, pause: state.paused }
  if (!state.playing || state.busy || state.waiting) return { go: false, pause: null }
  if (state.error) return { go: false, pause: { kind: 'error', text: state.error } }
  return { go: true, pause: null }
}

/** Watch as the screen reads it: the timer, and the backend's pause only while in Watch. */
export function watchOf(on: boolean, data?: WatchState): WatchState {
  return { seconds: data?.seconds ?? 0, paused: on ? data?.paused ?? null : null }
}

/** The timer choices in Watch, in seconds; 0 plays by hand only (Next). */
export const WATCH_SECONDS = [0, 10, 20, 40, 60]

/** How a story line opening a round turn reads: a player's line, the author's nudge, or nothing (a Watch turn and an
 *  Author turn with no nudge open on an empty line). */
export function openingKind(message: { role: string; text: string; mode?: Mode | null }): 'line' | 'nudge' | 'none' {
  if (message.role !== 'user') return 'line'
  if (!message.text.trim()) return 'none'
  return message.mode === 'author' ? 'nudge' : 'line'
}

/** The motives the minds panel may show (GET /api/minds gives them only in Author and Watch), by character. */
export function motivesOf(rows: MindRow[] | undefined): Record<string, string> {
  return Object.fromEntries((rows ?? []).filter((row) => row.motive).map((row) => [row.key, row.motive!]))
}

/** Whether leaving Play asks "Show the motives you missed?": only from Play, and only while the campaign has no answer
 *  yet (GET /api/minds `reveal_missed` is null; a backend without it never asks). */
export function asksMissed(from: Mode, to: Mode, reveal: boolean | null | undefined): boolean {
  return from === 'play' && to !== 'play' && reveal === null
}

// The Author's hand (GET /api/rounds/author) -----------------------------------------------------------------------------

/** A planned beat on the beat board: cut, given to the director's note (`used`), or on the page (`landed`). */
export interface BoardBeat { id: string; text: string; cut: boolean; used: boolean; landed: boolean; source: string }
/** One arc's beats for its stage, the spine first. */
export interface BoardArc { arc_id: string; name: string; stage: number; spine: boolean; beats: BoardBeat[] }
/** A beat the user would like to see, waiting in the nudge box for the next Play turn. */
export interface BoxBeat { id: string; text: string; created_at: string }
export interface AuthorView { board: BoardArc[]; box: BoxBeat[]; editable: boolean; feedback: { nudge: string; status: 'used' | 'not_yet'; why: string }[] }

/** The nudge box holds this many beats at a time (adventure/rounds/author.py MOST_BOX). */
export const MOST_BOX = 6

/** Where a planned beat stands, for its mark on the board: on the page, used, or nothing yet. */
export function beatStanding(beat: BoardBeat): 'landed' | 'used' | null {
  if (beat.landed) return 'landed'
  return beat.used ? 'used' : null
}

/** Whether a beat can move up or down its arc's plan. */
export function beatMoves(index: number, count: number): { up: boolean; down: boolean } {
  return { up: index > 0, down: index < count - 1 }
}
