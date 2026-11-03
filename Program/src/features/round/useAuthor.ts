import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api'
import type { AuthorView } from './round'
import { ROUND_KEY } from './useRound'

export const AUTHOR_KEY = [...ROUND_KEY, 'author']

/** GET /api/rounds/author and its edits: the beat board in Author (add, cut, move), and the nudge box in Play. Each
 *  edit answers with the whole view, which replaces the cached one; a refusal goes to `onError`. */
export function useAuthor(onError: (text: string) => void) {
  const client = useQueryClient()
  const author = useQuery({ queryKey: AUTHOR_KEY, queryFn: () => api<AuthorView>('/rounds/author') })
  const change = async (request: Promise<AuthorView>): Promise<boolean> => {
    try { client.setQueryData(AUTHOR_KEY, await request); return true }
    catch (failure) { onError(failure instanceof Error ? failure.message : 'Not changed'); return false }
  }
  return {
    view: author.data,
    addBeat: (arc_id: string, text: string) => change(api<AuthorView>('/rounds/author/beats', { arc_id, text })),
    cut: (id: string, cut: boolean) => change(api<AuthorView>(`/rounds/author/beats/${id}`, { cut }, 'PATCH')),
    move: (id: string, position: number) => change(api<AuthorView>(`/rounds/author/beats/${id}`, { position }, 'PATCH')),
    wish: (text: string) => change(api<AuthorView>('/rounds/author/box', { text })),
    unwish: (id: string) => change(api<AuthorView>(`/rounds/author/box/${id}`, undefined, 'DELETE')),
  }
}
