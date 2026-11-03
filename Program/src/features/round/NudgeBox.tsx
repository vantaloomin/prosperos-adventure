import { useState } from 'react'
import { Plus, X } from 'lucide-react'
import { AddLine } from './AddLine'
import { MOST_BOX } from './round'
import { useAuthor } from './useAuthor'

/** In Play, under the line: beats the user would like to see (a storm, a stranger arriving). The next turn takes them
 *  as the brief's user-set beats and they leave the box once it is written (adventure/rounds/author.py). */
export function NudgeBox({ onError }: { onError: (text: string) => void }) {
  const author = useAuthor(onError)
  const [adding, setAdding] = useState(false)
  const box = author.view?.box ?? []
  if (!author.view) return null
  const room = box.length < MOST_BOX
  return <div className="nudge-box" role="group" aria-label="Beats you would like">
    {box.map((beat) => <span key={beat.id} className="receipt-chip">
      {beat.text}
      <button type="button" aria-label={`Remove "${beat.text}"`} onClick={() => void author.unwish(beat.id)}><X aria-hidden="true" /></button>
    </span>)}
    {room && (adding
      ? <AddLine label="A beat you would like" placeholder="A beat you'd like to see" autoFocus onAdd={author.wish} />
      : <button type="button" className="text-button" onClick={() => setAdding(true)}><Plus aria-hidden="true" />Beat</button>)}
  </div>
}
