// The round loop's words on the play screen and in Settings (docs/style-guide.md "Copy"). Kept free of React, so
// tests/ui can load it directly.
import { decidedCount, rowStatus, seatName, stepAt, type AgentPace, type Awaiting, type Loyalty, type Mode, type PresetKey, type RoundLive, type RoundState, type RoundTable } from './round.ts'

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
