/** Applying and undoing a Sidebar Assistant proposal, each through the app's own paths: the author's note, Switch
 * wording, the journal, the lore, and the GM view's feelings and planned beats (docs/assistant.md). */
import type { QueryClient } from '@tanstack/react-query'
import { api } from '../../api'
import type { Journal } from '../../types'
import { saveNote } from '../story/noteApi'
import { noteKey } from '../story/noteState'
import { STORY_KEY } from '../story/table'
import { addedFact, type Change, type Proposal } from './proposals'

const JOURNAL_KEY = ['story-journal']
const GM_KEY = ['story-gm']
const LORE_KEY = ['lore']
const CHAT = 'story'

/** Applies a change and returns what Undo needs: the id of what it created, where it created something. */
export async function apply(change: Change, client: QueryClient): Promise<string | undefined> {
  switch (change.kind) {
    case 'authors_note':
      client.setQueryData(noteKey(CHAT), await saveNote(CHAT, change.text, true))
      return undefined
    case 'narration':
      client.setQueryData(STORY_KEY, await api(`/story/messages/${change.message_id}/reword`, { text: change.text, expected: change.before }))
      return undefined
    case 'journal_add': {
      const journal = await api<Journal>('/story/journal', { subject: change.subject, text: change.text })
      client.setQueryData(JOURNAL_KEY, journal)
      return addedFact(journal, change.subject, change.text)
    }
    case 'journal_fix':
      client.setQueryData(JOURNAL_KEY, await api<Journal>(`/story/journal/${change.entry_id}`, { text: change.text }, 'PATCH'))
      return undefined
    case 'lore_add': {
      const { added, ...lore } = await api<{ added: string }>('/lore/entries', { title: change.title, text: change.text, keywords: change.keywords, always: change.always, visibility: change.visibility })
      client.setQueryData(LORE_KEY, lore)
      return added
    }
    case 'feelings':
      client.setQueryData(GM_KEY, await api(`/story/gm/people/${encodeURIComponent(change.key)}`, change.values, 'PATCH'))
      return undefined
    case 'beat_cut':
      client.setQueryData(GM_KEY, await api(`/story/gm/beats/${change.beat_id}`, { cut: change.cut }, 'PATCH'))
      return undefined
    case 'beat_add': {
      const { added, ...gm } = await api<{ added: string }>('/story/gm/beats', { arc_id: change.arc_id, text: change.text })
      client.setQueryData(GM_KEY, gm)
      return added
    }
  }
}

/** Puts back what an applied proposal changed. */
export async function undo(proposal: Proposal, client: QueryClient): Promise<void> {
  const { change, undo: created } = proposal
  switch (change.kind) {
    case 'authors_note':
      client.setQueryData(noteKey(CHAT), await saveNote(CHAT, change.before, change.enabled))
      return
    case 'narration':
      client.setQueryData(STORY_KEY, await api(`/story/messages/${change.message_id}/switch`, {}))
      return
    case 'journal_add':
      if (!created) throw new Error('Remove it from the journal instead.')
      client.setQueryData(JOURNAL_KEY, await api<Journal>(`/story/journal/${created}`, undefined, 'DELETE'))
      return
    case 'journal_fix':
      client.setQueryData(JOURNAL_KEY, await api<Journal>(`/story/journal/${change.entry_id}`, { text: change.before }, 'PATCH'))
      return
    case 'lore_add':
      client.setQueryData(LORE_KEY, await api(`/lore/entries/${created}`, undefined, 'DELETE'))
      return
    case 'feelings':
      client.setQueryData(GM_KEY, await api(`/story/gm/people/${encodeURIComponent(change.key)}`, change.before, 'PATCH'))
      return
    case 'beat_cut':
      client.setQueryData(GM_KEY, await api(`/story/gm/beats/${change.beat_id}`, { cut: !change.cut }, 'PATCH'))
      return
    case 'beat_add':
      client.setQueryData(GM_KEY, await api(`/story/gm/beats/${created}`, undefined, 'DELETE'))
  }
}
