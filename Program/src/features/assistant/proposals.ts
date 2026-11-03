/** What the Sidebar Assistant proposes and how each proposal reads (adventure/assistant.py, docs/assistant.md).
 * Nothing here talks to the server. */
import type { FeelingAxis, Journal } from '../../types'

export type Change =
  | { kind: 'authors_note'; before: string; enabled: boolean; text: string }
  | { kind: 'narration'; message_id: string; before: string; text: string }
  | { kind: 'journal_add'; subject: string; text: string }
  | { kind: 'journal_fix'; entry_id: string; subject: string; before: string; text: string }
  | { kind: 'lore_add'; title: string; text: string; keywords: string[]; always: boolean; visibility: 'public' | 'gm' }
  | { kind: 'feelings'; key: string; name: string; before: Record<FeelingAxis, number>; values: Partial<Record<FeelingAxis, number>> }
  | { kind: 'beat_cut'; beat_id: string; arc: string; text: string; cut: boolean }
  | { kind: 'beat_add'; arc_id: string; arc: string; text: string }

export interface AssistantReply { reply: string; changes: Change[]; gm: boolean }
export type ProposalStatus = 'pending' | 'working' | 'applied' | 'dismissed'
/** `undo` is what putting it back needs: the id the change created, where it created one. */
export interface Proposal { id: string; change: Change; status: ProposalStatus; undo?: string; error?: string }
export interface Turn { id: string; message: string; reply: string; proposals: Proposal[] }
export interface HistoryTurn { role: 'user' | 'assistant'; content: string }

const HISTORY_TURNS = 5
const HISTORY_CHARS = 4000
/** GM edits: shown with a mark, and applied only while the GM view is on (the server checks too). */
export const GM_KINDS: Change['kind'][] = ['feelings', 'beat_cut', 'beat_add']

export function proposals(changes: Change[], id: () => string): Proposal[] {
  return changes.map((change) => ({ id: id(), change, status: 'pending' as const }))
}

/** The words before the change, for Compare; '' where there were none. */
export function before(change: Change): string {
  if (change.kind === 'feelings') return feelingsText(change.before, Object.keys(change.values) as FeelingAxis[])
  return 'before' in change ? change.before : ''
}

export function after(change: Change): string {
  if (change.kind === 'feelings') return feelingsText({ ...change.before, ...change.values }, Object.keys(change.values) as FeelingAxis[])
  return change.text
}

function feelingsText(values: Record<FeelingAxis, number>, axes: FeelingAxis[]): string {
  return axes.map((axis) => `${axis} ${values[axis]}`).join(', ')
}

type Of<K extends Change['kind']> = Extract<Change, { kind: K }>
type Wording = { [K in Change['kind']]: (change: Of<K>) => string }

const quoted = (words: string[]) => words.map((word) => `\u201c${word}\u201d`).join(' or ')

const TITLES: Wording = {
  authors_note: () => "Author's note",
  narration: () => 'The narrator\u2019s passage in new words',
  journal_add: (change) => `New journal fact: ${change.subject}`,
  journal_fix: (change) => `Journal fact: ${change.subject}`,
  lore_add: (change) => `New lore${change.title ? `: ${change.title}` : ''}`,
  feelings: (change) => `How ${change.name} feels`,
  beat_cut: (change) => `${change.cut ? 'Cut' : 'Bring back'} a beat in ${change.arc}`,
  beat_add: (change) => `New beat in ${change.arc}`,
}

/** One line on what applying does. */
const EFFECTS: Wording = {
  authors_note: () => 'Switches the note on; it steers every narration until you change it.',
  narration: () => 'The dice and what happened stay. Switch wording under the passage puts the old words back.',
  journal_add: () => 'The narrator reads it as something your character knows.',
  journal_fix: () => 'The correction is logged, like one made in the journal.',
  lore_add: (change) => `${change.always ? 'Always on.' : `Comes in when the story says ${quoted(change.keywords)}.`}${change.visibility === 'gm' ? ' GM only: no character reads it.' : ''}`,
  feelings: () => 'A GM edit: it changes how they treat your character from now on.',
  beat_cut: (change) => change.cut ? 'A GM edit: the director skips it.' : 'A GM edit: the director can use it again.',
  beat_add: () => 'A GM edit: the director gives it when the arc is due.',
}

function worded(table: Wording, change: Change): string {
  return (table[change.kind] as (change: Change) => string)(change)
}

export const title = (change: Change) => worded(TITLES, change)
export const effect = (change: Change) => worded(EFFECTS, change)

/** Whether Compare has two wordings to show. */
export function comparable(change: Change): boolean {
  return ['authors_note', 'narration', 'journal_fix', 'feelings'].includes(change.kind) && !!before(change)
}

/** What the server is sent of the conversation so far: the latest turns, each cut to a readable length. */
export function history(turns: Turn[]): HistoryTurn[] {
  return turns.slice(-HISTORY_TURNS).flatMap((turn) => [
    { role: 'user' as const, content: turn.message.slice(0, HISTORY_CHARS) },
    { role: 'assistant' as const, content: turn.reply.slice(0, HISTORY_CHARS) },
  ]).filter((turn) => turn.content.trim())
}

export function withProposal(turns: Turn[], proposalId: string, change: Partial<Proposal>): Turn[] {
  return turns.map((turn) => ({ ...turn, proposals: turn.proposals.map((item) => item.id === proposalId ? { ...item, ...change } : item) }))
}

/** The new journal fact among the entries that came back, newest first: the first with its subject and words. */
export function addedFact(journal: Journal, subject: string, text: string): string | undefined {
  return journal.entries.find((entry) => entry.subject === subject && entry.text === text)?.id
}
