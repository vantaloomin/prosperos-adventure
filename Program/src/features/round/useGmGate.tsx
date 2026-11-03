import { useState } from 'react'
import { api, ApiError } from '../../api'
import { GmAsk } from './GmGate'
import { useRoundTable } from './useRound'
import { ASKS_FIRST, hasAgents, type GmRound } from './round'

/** In Play with characters who think, the GM view asks first (docs/spec.md "Waiting and pauses"): `open` resolves true
 *  once it may open, after the question when the story still needs the user's yes, and false when they cancel. The
 *  turn it opens on is marked (adventure/gm.py). With nobody thinking it opens as it always has. */
export function useGmGate() {
  const table = useRoundTable()
  const [asking, setAsking] = useState<{ question: string; answer: (open: boolean) => void } | null>(null)
  const open = async (): Promise<boolean> => {
    if (!hasAgents(table.data)) return true
    try {
      await api<GmRound>('/gm/round', { confirmed: false, remember: false })
      return true
    } catch (failure) {
      if (!(failure instanceof ApiError) || failure.code !== ASKS_FIRST) throw failure
      return new Promise<boolean>((resolve) => setAsking({ question: failure.message, answer: resolve }))
    }
  }
  const answer = async (yes: boolean, remember: boolean) => {
    const waiting = asking
    setAsking(null)
    if (yes) await api<GmRound>('/gm/round', { confirmed: true, remember })
    waiting?.answer(yes)
  }
  return { open, dialog: asking && <GmAsk question={asking.question} onAnswer={(yes, remember) => void answer(yes, remember)} /> }
}
