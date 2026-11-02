import { api } from '../../api'
import type { AuthorsNoteState } from './noteState'

export function saveNote(chat: string, text: string, enabled: boolean) {
  return api<AuthorsNoteState>(`/authors-notes/${chat}`, { text, enabled }, 'PUT')
}
