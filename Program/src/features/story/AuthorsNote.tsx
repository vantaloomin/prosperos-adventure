import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { FileText } from 'lucide-react'
import { api } from '../../api'
import { saveNote } from './noteApi'
import { NOTE_LIMIT, NOTE_SWITCH, noteKey, noteLook, type AuthorsNoteState, type Look } from './noteState'
import { ErrorNotice } from '../../components/ErrorNotice'

const COUNT_FROM = 800
const SAVE_AFTER_MS = 600
const PHONE = '(max-width: 720px)'
const SPOKEN: Record<Look, string> = { off: 'empty', on: 'on', paused: 'off' }
const RETRO: Record<Look, string> = { off: '[note]', on: '[note on]', paused: '[note off]' }

/** The note button left of the message box, and the note itself: a tray pulled up over the bottom of the chat on a
 * computer, a sheet from the bottom of the screen on a phone. What is typed saves itself; nothing to confirm. */
export function AuthorsNote({ chat, name, story = false }: { chat: string; name: string; story?: boolean }) {
  const note = useNote(chat)
  const dialog = useRef<HTMLDialogElement>(null)
  const button = useRef<HTMLButtonElement>(null)
  const area = useRef<HTMLTextAreaElement>(null)
  const [open, setOpen] = useState(false)
  const look = noteLook(note.text, note.enabled)
  const show = () => {
    const element = dialog.current
    if (!element) return
    if (window.matchMedia(PHONE).matches) element.showModal(); else element.show()
    setOpen(true)
    const box = area.current
    if (box) { box.focus({ preventScroll: true }); box.setSelectionRange(box.value.length, box.value.length) }
  }
  const close = () => { dialog.current?.close() }
  useEffect(() => {
    if (!open) return
    // The tray on a computer is not modal, so Escape is ours to handle.
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') { event.preventDefault(); close() } }
    document.addEventListener('keydown', escape)
    return () => document.removeEventListener('keydown', escape)
  }, [open])
  // The box grows with the note (up to its maximum height in styles.css), so a long note reads whole.
  useLayoutEffect(() => {
    const box = area.current
    if (!box || !open) return
    box.style.height = 'auto'
    box.style.height = `${box.scrollHeight + box.offsetHeight - box.clientHeight}px`
  }, [note.text, open])
  const first = note.text.trim().split('\n')[0]
  return <>
    <button ref={button} type="button" className="button composer-note" data-state={look} aria-expanded={open} aria-controls={`note-${chat}`}
      aria-label={`Author's note, ${SPOKEN[look]}`} title={look === 'off' ? "Author's note" : `Author's note: ${first.slice(0, 60)}${first.length > 60 ? '…' : ''}`}
      onClick={() => (open ? close() : show())}>
      <FileText aria-hidden="true" /><span className="note-retro" aria-hidden="true">{RETRO[look]}</span>
    </button>
    <dialog ref={dialog} id={`note-${chat}`} className="note-tray" aria-label="Author's note"
      onClose={() => { setOpen(false); note.flush(); button.current?.focus({ preventScroll: true }) }}
      onClick={(event) => { if (event.target === event.currentTarget) close() }}>
      <div className="note-body">
        <span className="note-grabber phone-only" aria-hidden="true" />
        <div className="note-head">
          <strong>Author's note</strong>
          <label className="note-switch"><input type="checkbox" role="switch" checked={note.enabled} onChange={(event) => note.change(note.text, event.target.checked, true)} /> {NOTE_SWITCH}</label>
        </div>
        <label className="visually-hidden" htmlFor={`note-text-${chat}`}>Author's note for this chat</label>
        <textarea ref={area} id={`note-text-${chat}`} className={note.enabled ? undefined : 'note-unused'} value={note.text} maxLength={NOTE_LIMIT} rows={4} aria-describedby={`note-help-${chat}`}
          placeholder={story ? 'Steer the story for every narration. It never shows in the story.' : `Steer the scene for every reply in this chat. ${name} won't see it as a message.`}
          onChange={(event) => note.change(event.target.value, note.enabled)} />
        {note.text.length > COUNT_FROM && <span className="note-count subtle" aria-live="polite">{note.text.length} / {NOTE_LIMIT}</span>}
        {note.error instanceof Error && <ErrorNotice error={note.error} />}
        <div className="note-foot">
          <span id={`note-help-${chat}`} className="subtle">{story ? 'This story only. Sent with every narration, never saved as a message or memory.' : 'This chat only. Sent with every reply, never saved as a message or memory.'}</span>
          <button type="button" className="text-button note-clear" disabled={!note.text} onClick={() => { note.change('', note.enabled, true); area.current?.focus() }}>Clear</button>
        </div>
        <button type="button" className="button primary note-done phone-only" onClick={close}>Done</button>
      </div>
    </dialog>
  </>
}

/** The note as typed, saved a moment after typing stops (and at once for the switch, Clear and closing). */
function useNote(chat: string) {
  const client = useQueryClient()
  const stored = useQuery({ queryKey: noteKey(chat), queryFn: () => api<AuthorsNoteState>(`/authors-notes/${chat}`) })
  const [draft, setDraft] = useState<{ text: string; enabled: boolean } | null>(null)
  const [error, setError] = useState<unknown>(null)
  const timer = useRef<number | undefined>(undefined)
  const pending = useRef<{ text: string; enabled: boolean } | null>(null)
  const write = () => {
    window.clearTimeout(timer.current)
    const value = pending.current
    if (!value) return
    pending.current = null
    saveNote(chat, value.text, value.enabled).then((saved) => {
      setError(null)
      client.setQueryData(noteKey(chat), saved)
      // Saved as typed: the stored note shows again, unless more
      // was typed while it saved.
      if (!pending.current) setDraft(null)
    }, setError)
  }
  // Leaving the chat saves what was typed (each chat mounts its own note: `key` is the chat).
  useEffect(() => () => write(), []) // eslint-disable-line react-hooks/exhaustive-deps
  const change = (text: string, enabled: boolean, now = false) => {
    setDraft({ text, enabled })
    pending.current = { text, enabled }
    window.clearTimeout(timer.current)
    if (now) write(); else timer.current = window.setTimeout(write, SAVE_AFTER_MS)
  }
  const shown = draft ?? stored.data ?? { text: '', enabled: true }
  return { text: shown.text, enabled: shown.enabled, change, flush: write, error }
}
