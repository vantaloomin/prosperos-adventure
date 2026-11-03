import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { ROUND_KEY, useRoundTable } from './useRound'
import { hasAgents, seatName, type GmRound } from './round'
import { GM_NAMES, mindLines } from './roundText'

export function GmAsk({ question, onAnswer }: { question: string; onAnswer: (yes: boolean, remember: boolean) => void }) {
  const [remember, setRemember] = useState(false)
  return (
    <ConfirmDialog title={question} onClose={() => onAnswer(false, false)} actions={<>
      <button type="button" className="button" onClick={() => onAnswer(false, false)}>{GM_NAMES.cancel}</button>
      <button type="button" className="button primary" onClick={() => onAnswer(true, remember)}>{GM_NAMES.open}</button>
    </>}>
      <label className="toggle"><input type="checkbox" checked={remember} onChange={(event) => setRemember(event.target.checked)} />{GM_NAMES.remember}</label>
    </ConfirmDialog>
  )
}

/** Inside the GM view, with characters who think: each one's intent, lines, whispers and motive this turn, revealed. */
export function GmRoundMinds() {
  const table = useRoundTable()
  const agents = hasAgents(table.data)
  const view = useQuery({ queryKey: [...ROUND_KEY, 'gm'], queryFn: () => api<GmRound>('/gm/round', { confirmed: true, remember: false }), enabled: agents })
  const minds = view.data?.minds ?? []
  if (!agents || !minds.length) return null
  const name = (key: string) => seatName(table.data, key)
  return (
    <section aria-label={GM_NAMES.turn}>
      <h3>{GM_NAMES.turn}</h3>
      <ul>{minds.map((row) => <li key={row.key}>
        <p><strong>{row.name}</strong></p>
        {mindLines(row, name).map((line, index) => <p key={index} className="subtle">{line}</p>)}
        {row.motive && <p className="gm-motive">{row.motive}</p>}
      </li>)}</ul>
    </section>
  )
}
