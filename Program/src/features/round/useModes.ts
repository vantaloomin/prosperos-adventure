import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api'
import { hasAgents, modeChosen, watchNext, type AgentPace, type LineMarks, type Mode, type RoundTable, type WatchPause } from './round'
import { PACE_KEY, ROUND_KEY } from './useRound'

/** The mode switcher's part: shown only once anyone at the table thinks, so a campaign without agents is Dungeon's. */
export function useMode(table: RoundTable | undefined, onError: (text: string) => void) {
  const client = useQueryClient()
  const change = (mode: Mode) => void api<RoundTable>('/rounds/settings', { mode }, 'PUT')
    .then((data) => client.setQueryData(ROUND_KEY, data),
      (failure: unknown) => onError(failure instanceof Error ? failure.message : 'Not changed'))
  const shown = hasAgents(table)
  // The mode turns are played in now; without agents, always Play.
  const active: Mode = shown ? table?.settings.mode ?? 'play' : 'play'
  return { shown, mode: modeChosen(table), active, change, head: table?.head ?? null }
}

/** `clear` puts away the last turn's error before playing again. The turn runner reads the pace again as each turn
 *  ends (Story.tsx `run`), so the cap is known before the next one starts. */
interface WatchProps { on: boolean; busy: boolean; waiting: boolean; error: string; next: () => void; clear: () => void }

/** Watch's Play / Pause: while playing, the next turn starts as soon as the last is written, until the user pauses,
 *  a turn fails, or the session reaches its token cap; the last two pause with a banner saying so. */
export function useWatch({ on, busy, waiting, error, next, clear }: WatchProps) {
  const [playing, setPlaying] = useState(false)
  const [pause, setPause] = useState<WatchPause>(null)
  const pace = useQuery({ queryKey: PACE_KEY, queryFn: () => api<AgentPace>('/agents'), enabled: on })
  const step = watchNext({ playing: on && playing, busy: busy || pace.isFetching, waiting, capped: !!pace.data?.capped, error })
  useEffect(() => {
    if (step.go) next()
  }, [step.go]) // eslint-disable-line react-hooks/exhaustive-deps -- one turn each time play may go on
  if (step.pause && playing) { setPlaying(false); setPause(step.pause) }
  return {
    playing: on && playing, pause,
    /** The pause banner says why play stopped, so the error is not said twice. */
    hides: (text: string) => pause ? '' : text,
    play: () => { clear(); setPause(null); setPlaying(true) },
    stop: () => { setPlaying(false); setPause(null) },
  }
}

/** The turns the GM view was open on (GET /api/gm/round/marks), once anyone at the table thinks; null otherwise, so a
 *  campaign without agents shows its lines as before. */
export function useLineMarks(table?: RoundTable): LineMarks | null {
  const agents = hasAgents(table)
  const marks = useQuery({ queryKey: [...ROUND_KEY, 'marks'], queryFn: () => api<{ marked: string[] }>('/gm/round/marks'), enabled: agents })
  return agents ? { table, marked: marks.data?.marked ?? [] } : null
}
