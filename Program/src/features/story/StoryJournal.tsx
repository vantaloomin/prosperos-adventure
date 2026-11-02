import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api'
import type { Journal, JournalEntry, JournalInstitution, JournalQuest, JournalThread } from '../../types'
import { Notice } from '../../components/Feedback'
import { Toggle } from '../../components/Fields'
import { StoryGm } from './StoryGm'
import { institutionLine, journalKind, questState, threadKind, todayLine } from './storyText'
import { useTable } from './table'

const JOURNAL_KEY = ['story-journal']

/** What your character knows (dungeon/record.py): facts the game keeps, which you can correct or add to. The GM view
 * shows the whole record, hidden truth included, and can ask the model again for one fact it pulled from the story. */
export function StoryJournal({ open }: { open?: boolean }) {
  const client = useQueryClient()
  const journal = useQuery({ queryKey: JOURNAL_KEY, queryFn: () => api<Journal>('/story/journal') })
  const table = useTable()
  const [error, setError] = useState('')
  const change = async (request: () => Promise<Journal>) => {
    setError('')
    try { client.setQueryData(JOURNAL_KEY, await request()) }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'That was not saved.') }
  }
  if (!journal.data) return null
  const { entries, quests, institutions = [], threads = [], gm = false, summary = '' } = journal.data
  const setGm = async (checked: boolean) => {
    setError('')
    try { await table.save({ gm_view: checked }) }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'That setting was not saved.') }
  }
  return (
    <details className="story-people" open={open}>
      <summary>{gm ? 'The whole record' : 'What you know'} ({entries.length})</summary>
      <Toggle label="GM view" hint="Shows everything the game keeps, secrets your character does not know included, so you can fix the model's mistakes. It spoils the story."
        checked={gm} onChange={(checked) => void setGm(checked)} />
      <Behind gm={gm} summary={summary} />
      <GoingOn institutions={institutions} quests={quests} threads={threads} />
      <ul>
        {entries.map((entry) => <JournalLine key={entry.id} entry={entry}
          onSave={(text) => change(() => api<Journal>(`/story/journal/${entry.id}`, { text }, 'PATCH'))}
          onAskAgain={gm && entry.pulled ? () => void change(() => api<Journal>(`/story/journal/${entry.id}/regenerate`, undefined, 'POST')) : undefined}
          onRemove={() => void change(() => api<Journal>(`/story/journal/${entry.id}`, undefined, 'DELETE'))} />)}
      </ul>
      <AddNote onAdd={(subject, text) => change(() => api<Journal>('/story/journal', { subject, text }))} />
      {error && <Notice tone="error">{error}</Notice>}
    </details>
  )
}

/** The GM view's panel while it is on, and the story so far as the narrator keeps it. */
function Behind({ gm, summary }: { gm: boolean; summary: string }) {
  return <>
    {gm && <StoryGm />}
    {summary && <details><summary>The story so far</summary><p className="story-note">{summary}</p></details>}
  </>
}

/** What is going on: schools and guilds, quests, and loose ends, each when there are any. */
function GoingOn({ institutions, quests, threads }: { institutions: JournalInstitution[]; quests: JournalQuest[]; threads: JournalThread[] }) {
  return <>
    {!!institutions.length && <Schools institutions={institutions} />}
    {!!quests.length && <Underway quests={quests} />}
    {!!threads.length && <Threads threads={threads} />}
  </>
}

/** The schools and guilds your character belongs to (dungeon/institutions.py): the term, grades and today's classes. */
function Schools({ institutions }: { institutions: JournalInstitution[] }) {
  return (
    <ul aria-label="School and duties">
      {institutions.map((item) => <li key={item.id}>
        <p className="subtle">{institutionLine(item)}</p>
        <p><strong>{item.name}</strong></p>
        {item.term && <p>{todayLine(item)}</p>}
      </li>)}
    </ul>
  )
}

/** The quests your character knows of (dungeon/quests.py), with the story time left. */
function Underway({ quests }: { quests: JournalQuest[] }) {
  return (
    <ul aria-label="Underway">
      {quests.map((quest) => <li key={quest.id}>
        <p className="subtle">{questState(quest)}</p>
        <p><strong>{quest.title}</strong></p>
        <p>{quest.status === 'open' ? quest.hook : quest.outcome}</p>
      </li>)}
    </ul>
  )
}

/** The loose ends your character has come across (dungeon/director.py), as they understand them. */
function Threads({ threads }: { threads: JournalThread[] }) {
  return (
    <ul aria-label="Loose ends">
      {threads.map((thread) => <li key={thread.id}>
        <p className="subtle">{threadKind(thread.kind)}</p>
        <p><strong>{thread.title}</strong></p>
        <p>{thread.seen}</p>
      </li>)}
    </ul>
  )
}

interface LineProps { entry: JournalEntry; onSave: (text: string) => Promise<void>; onRemove: () => void; onAskAgain?: () => void }

function JournalLine({ entry, onSave, onRemove, onAskAgain }: LineProps) {
  const [editing, setEditing] = useState<string | null>(null)
  return (
    <li>
      <p className="subtle">{journalKind(entry)}</p>
      {editing === null ? <p>{entry.text}</p>
        : <textarea aria-label={`What you know about ${entry.subject}`} rows={2} maxLength={500} value={editing}
          onChange={(event) => setEditing(event.target.value)} />}
      <div className="form-actions">
        {editing === null ? <>
          <button type="button" className="text-button" onClick={() => setEditing(entry.text)}>Correct</button>
          <button type="button" className="text-button" onClick={onRemove}>Remove</button>
          {onAskAgain && <button type="button" className="text-button" onClick={onAskAgain}>Ask again</button>}
        </> : <>
          <button type="button" className="text-button" disabled={!editing.trim()} onClick={() => void onSave(editing.trim()).then(() => setEditing(null))}>Save</button>
          <button type="button" className="text-button" onClick={() => setEditing(null)}>Cancel</button>
        </>}
      </div>
    </li>
  )
}

function AddNote({ onAdd }: { onAdd: (subject: string, text: string) => Promise<void> }) {
  const [subject, setSubject] = useState('')
  const [text, setText] = useState('')
  const ready = !!subject.trim() && !!text.trim()
  return (
    <form className="story-note-form" onSubmit={(event) => { event.preventDefault(); if (ready) void onAdd(subject.trim(), text.trim()).then(() => { setSubject(''); setText('') }) }}>
      <input aria-label="About" placeholder="About whom or what" maxLength={120} value={subject} onChange={(event) => setSubject(event.target.value)} />
      <input aria-label="What you know" placeholder="What you know" maxLength={500} value={text} onChange={(event) => setText(event.target.value)} />
      <button type="submit" className="button" disabled={!ready}>Add</button>
    </form>
  )
}
