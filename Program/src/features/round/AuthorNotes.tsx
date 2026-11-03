import { useQuery } from '@tanstack/react-query'
import { api } from '../../api'
import { ROUND_KEY } from './useRound'

/** GET /api/rounds/author `feedback`: for the newest turn, each nudge, whether it took, and the line saying so. */
interface Feedback { nudge: string; status: 'used' | 'not_yet'; why: string }

/** Under the nudge box in Author: whether the last nudge took ("Used: Mara took it up", "Not yet: no one took it up
 *  this turn"), from the turn's own feedback. */
export function AuthorNotes() {
  const author = useQuery({ queryKey: [...ROUND_KEY, 'author'], queryFn: () => api<{ feedback: Feedback[] }>('/rounds/author') })
  const lines = (author.data?.feedback ?? []).map((item) => item.why.replace(/\.$/, '')).filter(Boolean)
  if (!lines.length) return null
  return <div className="author-notes" role="status">{lines.map((line, index) => <p key={index}>{line}</p>)}</div>
}
