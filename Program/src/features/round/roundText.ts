// The round loop's words on the play screen and in Settings (docs/style-guide.md "Copy"). Kept free of React, so
// tests/ui can load it directly.
import { decidedCount, rowStatus, seatName, stepAt, type AgentPace, type Awaiting, type WatchPause, type Loyalty, type Mode, type PresetKey, type MindRow, type ReportRoll, type RoundLive, type RoundState, type RoundTable, type TurnReport } from './round.ts'

export const STEP_NAMES = { declare: 'Declare', react: 'React', talk: 'Talk', roll: 'Roll', write: 'Write' } as const

const STATE_NAMES: Partial<Record<RoundState, string>> = {
  gathering: 'Declaring', declaring: 'Declaring', reacting: 'Reacting', conversing: 'Talking', awaiting_user: 'Waiting for you',
  resolving: 'Rolling', writing: 'Writing', committing: 'Writing',
}

/** The lit step named under the timeline, with the count while declaring: "Declaring · 2 of 3". */
export function stepLine(state: RoundState | null, live: RoundLive): string {
  if (stepAt(state) < 0 || !state) return ''
  const { decided, of } = decidedCount(live)
  return state === 'declaring' && of ? `${STATE_NAMES[state]} · ${decided} of ${of}` : STATE_NAMES[state] ?? ''
}

/** A character's row this turn. In Play only that they decided, never what; in Author and Watch, their intent once it
 *  arrives. Null leaves the row as it was (what they're doing in the scene). */
export function rowText(key: string, live: RoundLive, mode: Mode, waiting: Awaiting | null): string | null {
  const status = rowStatus(key, live, waiting)
  if (status === 'decided') return mode !== 'play' && live.seats[key]?.intent ? live.seats[key].intent! : 'Decided'
  return status && ROW_NAMES[status]
}

const ROW_NAMES = { thinking: 'Thinking', fallback: 'Went by the rules', waiting: 'Waiting for you' } as const

/** The polite live region's summary: "3 of 5 characters have decided", or who is waiting for an answer. */
export function liveSummary(live: RoundLive, table: RoundTable | null | undefined, waiting: Awaiting | null): string {
  if (waiting) return `${seatName(table, waiting.speaker)} is waiting for you`
  const { decided, of } = decidedCount(live)
  if (!of) return ''
  return `${decided} of ${of} ${of === 1 ? 'character has' : 'characters have'} decided`
}

/** The accessible name of the dot on a portrait of a character who thinks for themself. */
export const THINKS_NAME = 'thinks for themself'
export const MIND_NAMES = { agent: 'Thinks', program: 'Rules' } as const

/** The reply card's words, with the user's character's name where they have one. */
export function replyText(you: string) {
  return {
    placeholder: you ? `What does ${you} say?` : 'What do you say?',
    letAnswer: you ? `Let ${you} answer` : 'Let your character answer',
    silent: 'Say nothing', reply: 'Reply', label: 'Your reply',
  }
}

/** The page title while a character waits on the user's answer, so a tab in the background shows it. */
export function titleWhile(waiting: boolean, title: string): string {
  const plain = title.replace(/^\(1\) /, '')
  return waiting ? `(1) ${plain}` : plain
}

// Pace -----------------------------------------------------------------------------------------------------------------

export const PRESET_NAMES: Record<PresetKey, string> = { quick: 'Quick', balanced: 'Balanced', rich: 'Rich' }
export const SCHEMING = ['Rarely', 'When it serves them', 'Readily', 'Always']
export const LOYALTY: { key: Loyalty; name: string }[] = [{ key: 'slow', name: 'Slowly' }, { key: 'steady', name: 'Steadily' }, { key: 'fast', name: 'Fast' }]
export const PACE_LABELS = {
  title: 'Pace', advanced: 'Advanced', agentCap: 'Thinking characters at once', converseCap: 'Exchanges per turn',
  scheming: 'Scheming', loyalty: 'Loyalties shift', sessionCap: 'Session cap in tokens', none: 'None',
}

const rounded = (tokens: number) => tokens >= 1000 ? `${Math.round(tokens / 1000)}k` : String(tokens)

/** A preset's estimate as data: "~43 s · 14 calls", or "~14 calls · 9k tokens" from a backend without the time. */
export function estimateLine(estimate: { calls: number; tokens: number; seconds?: number }): string {
  const calls = `${estimate.calls} ${estimate.calls === 1 ? 'call' : 'calls'}`
  return estimate.seconds ? `~${Math.round(estimate.seconds)} s · ${calls}` : `~${calls} · ${rounded(estimate.tokens)} tokens`
}

/** "12k of 200k tokens this session", or with no cap "12k tokens this session". */
export function spendLine(spend: AgentPace['spend']): string {
  return spend.cap ? `${rounded(spend.spent)} of ${rounded(spend.cap)} tokens this session` : `${rounded(spend.spent)} tokens this session`
}

// The turn report ------------------------------------------------------------------------------------------------------

export const REPORT_NAMES = {
  you: 'You', rolls: 'Rolls', motives: 'Motives', numbers: 'Numbers', inventions: 'Made up this turn', strike: 'Strike',
  struck: 'Struck', checks: 'Checks', offpage: 'Elsewhere', questions: 'Open questions', next: 'Next', corrections: 'Corrections',
  judged: 'Read from the story', undo: 'Undo', undone: 'Undone', cache: 'Model cache',
} as const

/** "Turn 12", the status line's link to the last turn's report. */
export const turnName = (number: number) => `Turn ${number}`

/** "Hesk · picks the lock · Deft · success, 16". */
export function rollLine(roll: ReportRoll, name: (key: string) => string): string {
  const result = roll.total === undefined ? roll.result : `${roll.result}, ${roll.total}`
  return [name(roll.actor), roll.action, roll.stat, result].filter(Boolean).join(' · ')
}

/** "2 rewrites · 1 sentence cut", or '' when the checks changed nothing. */
export function checksLine(checks: TurnReport['checks']): string {
  const parts = [checks.rewrites ? `${checks.rewrites} ${checks.rewrites === 1 ? 'rewrite' : 'rewrites'}` : '',
    checks.cut.length ? `${checks.cut.length} ${checks.cut.length === 1 ? 'sentence' : 'sentences'} cut` : '',
    checks.review.length ? `${checks.review.length} ${checks.review.length === 1 ? 'note' : 'notes'}` : '']
  return parts.filter(Boolean).join(' · ')
}

/** "64% of 12,400 prompt tokens read from cache · 7 calls · 3,100 written", "7 calls; the model service did not say
 *  what it cached", or '' for a turn with no model calls. */
export function cacheLine(cache: TurnReport['cache']): string {
  const calls = cache?.calls ?? 0
  if (!calls) return ''
  const callText = `${calls} ${calls === 1 ? 'call' : 'calls'}`
  if (!cache?.reported || !cache.input) return `${callText}; the model service did not say what it cached`
  const share = Math.round((cache.read ?? 0) / cache.input * 100)
  return [`${share}% of ${cache.input.toLocaleString('en-US')} prompt tokens read from cache`, callText,
    cache.written ? `${cache.written.toLocaleString('en-US')} written` : ''].filter(Boolean).join(' · ')
}

// The GM view in round play ------------------------------------------------------------------------------------------

export const GM_NAMES = { remember: "Don't ask again in this story", open: 'Open', cancel: 'Cancel', turn: 'This turn', whisper: 'whispers' } as const

/** A mind's row in the GM view: intent, each line said, each whisper, and the motive apart (shown in the warning tone). */
export function mindLines(row: MindRow, name: (key: string) => string): string[] {
  const to = (who: string[] | string | null) => (Array.isArray(who) ? who : who ? [who] : []).map(name).join(', ')
  return [row.intent ?? '', ...(row.lines ?? []).map((line) => `“${line.text}”${to(line.to) ? ` to ${to(line.to)}` : ''}`),
    ...(row.whispers ?? []).map((item) => `${GM_NAMES.whisper} “${item.text}”${to(item.to) ? ` to ${to(item.to)}` : ''}`)].filter(Boolean)
}

// Modes ---------------------------------------------------------------------------------------------------------------

export const MODE_NAMES = { play: 'Play', author: 'Author', watch: 'Watch' } as const
export const MODE_LABEL = 'Mode'
/** The composer in Author, where a line is the author's nudge to the story (PL-4). */
export const NUDGE = { placeholder: 'Nudge the story', label: 'Your nudge', send: 'Next' } as const

/** The composer's words: the player's line in Play, the author's nudge in Author, where Send with no nudge is Next. */
export function composerText(nudge: boolean, empty: boolean) {
  if (!nudge) return { label: 'What you do or say', placeholder: 'What do you do or say?', send: 'Send', max: 40000 }
  return { label: NUDGE.label, placeholder: NUDGE.placeholder, send: empty ? NUDGE.send : 'Send', max: 4000 }
}
export const WATCH_NAMES = {
  play: 'Play', pause: 'Pause', next: 'Next', label: 'Watch', raise: 'Raise cap', stop: 'Stop here', retry: 'Try again',
  go: 'Continue', author: 'Switch to Author', every: 'Every',
} as const

/** The pause banner's line, always with the reason (PL-10): "Paused: Mara betrayed the party". */
export function pauseLine(pause: Exclude<WatchPause, null>): string {
  return `Paused: ${pause.text.replace(/^Paused: /, '').replace(/\.$/, '')}`
}

/** A timer choice: "20 s", "1 min", or "By hand". */
export const secondsName = (seconds: number) => !seconds ? 'By hand' : seconds % 60 ? `${seconds} s` : `${seconds / 60} min`

/** On a story line whose turn had the GM view open: "GM view was open" (PL-12). */
export const MARK_NAMES = { gm: 'GM view was open', report: 'Report' } as const

/** The one question on leaving Play (PL-11); Keep hidden is the default. */
export const MISSED = { question: 'Show the motives you missed?', hide: 'Keep hidden', show: 'Show' } as const

// The Author's hand --------------------------------------------------------------------------------------------------

export const BEAT_MARKS = { landed: 'On the page', used: 'Used' } as const

// Asking again -------------------------------------------------------------------------------------------------------

/** A branch started by asking a character to decide again reads as a question (docs/spec.md "Branches read as
 *  questions"). It never says what they chose, which in Play stays theirs. */
export const whatIf = (name: string) => `What if ${name} had chosen otherwise?`
export const askAgain = (name: string) => `Ask ${name} again`

/** The cast page's bank (CA-8): the leads who don't join your party, and the buttons that move them. */
export const BANK_NAMES = {
  title: 'Bank', add: (name: string) => `Add ${name} to your party`, remove: (name: string) => `Move ${name} to the bank`,
} as const

/** A thinking character's notes and model, in their open row. */
export const SEAT_NAMES = {
  notes: (name: string) => `Your notes on ${name}`, notesHint: 'Notes', model: (name: string) => `Model for ${name}`, agentsModel: "Agents' model",
} as const
