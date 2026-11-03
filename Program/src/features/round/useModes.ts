import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api'
import { asksMissed, hasAgents, modeChosen, watchNext, watchOf, type LineMarks, type Mode, type RoundTable, type WatchPause, type WatchState } from './round'
import { ROUND_KEY } from './useRound'

/** GET /api/rounds/mode: who stands in for the user's character outside Play, the timer, and, once the backend keeps
 *  it, whether the newest switch out of Play has its missed-motives answer (null until answered). */
interface ModeView { settings: { stand_in: string; watch_seconds: number }; reveal_missed?: boolean | null; table?: RoundTable }

const MODE_KEY = [...ROUND_KEY, 'mode']

/** The mode switcher's part (PUT /api/rounds/mode): shown only once anyone at the table thinks, so a campaign without
 *  agents is Dungeon's. Leaving Play asks once, in the banner, whether to show the motives missed (PL-11). */
export function useMode(table: RoundTable | undefined, onError: (text: string) => void) {
  const client = useQueryClient()
  const shown = hasAgents(table)
  const [asking, setAsking] = useState(false)
  const failed = (failure: unknown) => onError(failure instanceof Error ? failure.message : 'Not changed')
  const change = async (mode: Mode) => {
    const from = modeChosen(table)
    try {
      const data = await api<ModeView>('/rounds/mode', { mode }, 'PUT')
      if (data.table) client.setQueryData(ROUND_KEY, data.table)
      const fresh = await client.fetchQuery({ queryKey: MODE_KEY, queryFn: () => api<ModeView>('/rounds/mode') })
      setAsking(asksMissed(from, mode, fresh.reveal_missed))
      await client.invalidateQueries({ queryKey: ROUND_KEY })
    } catch (failure) { failed(failure) }
  }
  const answer = (reveal: boolean) => {
    setAsking(false)
    void api('/rounds/mode/reveal', { reveal }, 'PUT').then(() => client.invalidateQueries({ queryKey: ROUND_KEY }), failed)
  }
  // The mode turns are played in now; without agents, always Play.
  const active: Mode = shown ? table?.settings.mode ?? 'play' : 'play'
  return { shown, mode: modeChosen(table), active, change: (mode: Mode) => void change(mode), head: table?.head ?? null, asking: asking && active !== 'play', answer }
}

/** The cast page's Play, Author and Watch (CA-6), before the story begins: the mode the first turn plays in and, outside
 *  Play, who stands in for the user's character (PUT /api/rounds/mode, /api/rounds/mode/settings). With no story yet
 *  there are no motives to miss, so leaving Play answers that question as Keep hidden. */
export function useCastMode(on: boolean, onError: (text: string) => void) {
  const client = useQueryClient()
  const view = useQuery({ queryKey: MODE_KEY, queryFn: () => api<ModeView & { coming?: Mode }>('/rounds/mode'), enabled: on })
  const put = (path: string, body: object) => void api(path, body, 'PUT')
    .then(() => client.invalidateQueries({ queryKey: ROUND_KEY }), (failure: unknown) => onError(failure instanceof Error ? failure.message : 'Not changed'))
  return {
    mode: view.data?.coming ?? 'play',
    standIn: view.data?.settings.stand_in === 'agent' ? 'agent' as const : 'program' as const,
    change: (mode: Mode) => put('/rounds/mode', { mode, reveal: false }),
    setStandIn: (mind: 'agent' | 'program') => put('/rounds/mode/settings', { stand_in: mind }),
  }
}

/** `next` plays the timer's turn (POST /api/rounds/watch/next/stream); `clear` puts away the last turn's error. */
interface WatchProps {
  on: boolean; busy: boolean; waiting: boolean; error: string; head: string | null
  next: () => void; clear: () => void; onError: (text: string) => void
}

/** Watch's Play / Pause (PL-10). While playing, the next turn starts `seconds` after the last is written, until Pause,
 *  a turn fails, or the backend pauses it (the session cap or a big moment); a pause shows one banner with why.
 *  Continue goes on from a big moment (POST /api/rounds/watch/continue). */
export function useWatch({ on, busy, waiting, error, head, next, clear, onError }: WatchProps) {
  const client = useQueryClient()
  const [playing, setPlaying] = useState(false)
  // The first turn after Play starts at once; the ones after it wait for the timer.
  const [first, setFirst] = useState(true)
  const state = useQuery({ queryKey: [...ROUND_KEY, 'watch'], queryFn: () => api<WatchState>('/rounds/watch'), enabled: on })
  const { seconds, paused } = watchOf(on, state.data)
  const going = on && playing
  const step = watchNext({ playing: going && seconds > 0, busy: busy || state.isFetching, waiting, paused, error })
  useEffect(() => {
    if (!step.go) return
    const timer = window.setTimeout(() => { setFirst(false); next() }, first ? 0 : seconds * 1000)
    return () => window.clearTimeout(timer)
  }, [step.go]) // eslint-disable-line react-hooks/exhaustive-deps -- one turn each time play may go on
  if (step.pause && going) setPlaying(false)
  const refresh = () => client.invalidateQueries({ queryKey: ROUND_KEY })
  return {
    playing: going, pause: step.pause, seconds,
    /** The pause banner says why play stopped, so the turn's error (or the timer's "Paused: …") is not said twice. */
    hides: (text: string) => quiet(step.pause, text) ? '' : text,
    play: () => { clear(); setFirst(true); setPlaying(true) },
    stop: () => { setPlaying(false); clear() },
    goOn: () => void api('/rounds/watch/continue', { against: step.pause?.turn_id ?? head }).then(() => { setFirst(true); setPlaying(true); return refresh() },
      (failure: unknown) => onError(failure instanceof Error ? failure.message : 'Not continued')),
    every: (value: number) => void api('/rounds/mode/settings', { watch_seconds: value }, 'PUT').then(refresh),
  }
}

function quiet(pause: WatchPause, text: string): boolean {
  return !!pause && (pause.kind === 'error' || text.startsWith('Paused: '))
}

/** The turns the GM view was open on (GET /api/gm/round/marks), once anyone at the table thinks; null otherwise, so a
 *  campaign without agents shows its lines as before. */
export function useLineMarks(table?: RoundTable): LineMarks | null {
  const agents = hasAgents(table)
  const marks = useQuery({ queryKey: [...ROUND_KEY, 'marks'], queryFn: () => api<{ marked: string[] }>('/gm/round/marks'), enabled: agents })
  return agents ? { table, marked: marks.data?.marked ?? [] } : null
}
