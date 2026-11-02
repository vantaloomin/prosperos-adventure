import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api'
import type { NotebookNote } from '../../types'
import { Notice } from '../../components/Feedback'

const NOTEBOOK_KEY = ['story-notebook']
type Notes = { notes: NotebookNote[] }

/** The player's own notebook (dungeon/chapters.py): across every branch, and no model ever reads it. */
export function StoryNotebook({ open }: { open?: boolean }) {
  const client = useQueryClient()
  const notebook = useQuery({ queryKey: NOTEBOOK_KEY, queryFn: () => api<Notes>('/story/notebook') })
  const [text, setText] = useState('')
  const [error, setError] = useState('')
  const change = async (request: () => Promise<Notes>) => {
    setError('')
    try { client.setQueryData(NOTEBOOK_KEY, await request()) }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'That was not saved.') }
  }
  if (!notebook.data) return null
  const { notes } = notebook.data
  return (
    <details className="story-people" open={open}>
      <summary>Your notebook ({notes.length})</summary>
      <p className="subtle">Only for you: it is kept across every branch, and the story never reads it.</p>
      <ul>
        {notes.map((note) => <NoteLine key={note.id} note={note}
          onSave={(changed) => change(() => api<Notes>(`/story/notebook/${note.id}`, { text: changed }, 'PATCH'))}
          onRemove={() => void change(() => api<Notes>(`/story/notebook/${note.id}`, undefined, 'DELETE'))} />)}
      </ul>
      <form className="story-add-form" onSubmit={(event) => { event.preventDefault(); if (text.trim()) void change(() => api<Notes>('/story/notebook', { text: text.trim() })).then(() => setText('')) }}>
        <textarea aria-label="A note for yourself" placeholder="A note for yourself" rows={3} maxLength={4000} value={text} onChange={(event) => setText(event.target.value)} />
        <button type="submit" className="button" disabled={!text.trim()}>Add</button>
      </form>
      {error && <Notice tone="error">{error}</Notice>}
    </details>
  )
}

function NoteLine({ note, onSave, onRemove }: { note: NotebookNote; onSave: (text: string) => Promise<void>; onRemove: () => void }) {
  const [editing, setEditing] = useState<string | null>(null)
  return (
    <li>
      {editing === null ? <p className="story-note">{note.text}</p>
        : <textarea aria-label="Your note" rows={3} maxLength={4000} value={editing} onChange={(event) => setEditing(event.target.value)} />}
      <div className="form-actions">
        {editing === null ? <>
          <button type="button" className="text-button" onClick={() => setEditing(note.text)}>Edit</button>
          <button type="button" className="text-button" onClick={onRemove}>Remove</button>
        </> : <>
          <button type="button" className="text-button" disabled={!editing.trim()} onClick={() => void onSave(editing.trim()).then(() => setEditing(null))}>Save</button>
          <button type="button" className="text-button" onClick={() => setEditing(null)}>Cancel</button>
        </>}
      </div>
    </li>
  )
}
