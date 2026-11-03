import { useQuery } from '@tanstack/react-query'
import { api } from '../../api'
import type { AuthorView } from './round'
import { AUTHOR_KEY } from './useAuthor'

/** Under the nudge box in Author: whether the last nudge took ("Used: Mara took it up", "Not yet: no one took it up
 *  this turn"), from the turn's own feedback. */
export function AuthorNotes() {
  const author = useQuery({ queryKey: AUTHOR_KEY, queryFn: () => api<AuthorView>('/rounds/author') })
  const lines = (author.data?.feedback ?? []).map((item) => item.why.replace(/\.$/, '')).filter(Boolean)
  if (!lines.length) return null
  return <div className="author-notes" role="status">{lines.map((line, index) => <p key={index}>{line}</p>)}</div>
}
