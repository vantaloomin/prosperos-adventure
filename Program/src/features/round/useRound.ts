import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api, streamApi, type StreamNote } from '../../api'
import { useWorlds } from '../worlds/useWorlds'
import { personaName } from '../worlds/worldsText'
import { hasAgents, modeOf, motivesOf, NO_ROUND, replyBody, roundAfter, roundStarting, seatChanges, seatName, waitingOn, type CastRound, type Mind, type MindRow, type ReplyKind, type RoundTable } from './round'
import { titleWhile } from './roundText'

export const ROUND_KEY = ['rounds']
/** The agents' pace and the session's spend (GET /api/agents). */
export const PACE_KEY = ['agents']
/** The user's own seat at the table, as the human, in Play. */
const YOU = 'you'

/** The table as it stands (GET /api/rounds): settings, seats, the turn under way and the newest turn. */
export function useRoundTable() {
  return useQuery({ queryKey: ROUND_KEY, queryFn: () => api<RoundTable>('/rounds') })
}

/** Writes seats one after another (the user's own seat first, so only one human ever sits) and keeps the table. */
function useSeats() {
  const client = useQueryClient()
  return async (changes: { key: string; body: { name: string; mind: Mind } }[]) => {
    for (const { key, body } of changes) {
      client.setQueryData(ROUND_KEY, await api<RoundTable>(`/rounds/seats/${encodeURIComponent(key)}`, body, 'PUT'))
    }
  }
}

/** While a character waits on the user's answer, the tab's title says so, for a tab in the background. */
function useTitleWhile(waiting: boolean) {
  useEffect(() => {
    document.title = titleWhile(waiting, document.title)
    return () => { document.title = titleWhile(false, document.title) }
  }, [waiting])
}

/** The round loop on the play screen: the table, what the stream has said of the turn under way (`hear` each event,
 *  `start` each stream), the reply card if one is up and how to answer it, and the cast list's part. */
export function useRoundPlay(onError: (text: string) => void) {
  const table = useRoundTable()
  const [live, setLive] = useState(NO_ROUND)
  const seat = useSeats()
  const you = personaName(useWorlds().data?.persona)
  const waiting = waitingOn(live, table.data)
  useTitleWhile(!!waiting)
  // The minds panel: motives outside Play, and whether the user has answered "Show the motives you missed?".
  const minds = useQuery({ queryKey: [...ROUND_KEY, 'minds'], queryFn: () => api<{ minds: MindRow[]; reveal_missed?: boolean | null }>('/minds'),
    enabled: hasAgents(table.data) })
  const cast: CastRound = {
    live, table: table.data, waiting: waiting?.awaiting ?? null, motives: modeOf(table.data) === 'play' ? {} : motivesOf(minds.data?.minds),
    onMind: (person, mind) => void seat(seatChanges(table.data, person, mind, { key: YOU, name: you || 'You' }))
      .catch((failure: unknown) => onError(failure instanceof Error ? failure.message : 'Not changed.')),
  }
  return {
    waiting, you, cast, revealMissed: minds.data?.reveal_missed,
    speaker: waiting ? seatName(table.data, waiting.awaiting.speaker) : '',
    start: () => setLive(roundStarting),
    hear: (event: unknown) => setLive((before) => roundAfter(before, event)),
    /** A turn's failure says nothing while the turn waits on the reply card: it is waiting, not lost. */
    shownError: (error: string) => waiting ? '' : error,
    /** The answer to the reply card, streamed as the turn goes on. */
    answer: (kind: ReplyKind, text: string, onText: (piece: string) => void, onNote: (note: StreamNote) => void) => {
      if (!waiting) return Promise.resolve()
      return streamApi(`/rounds/turns/${encodeURIComponent(waiting.turnId)}/reply/stream`,
        replyBody(waiting.awaiting, kind, text, waiting.turnId), onText, onNote)
    },
  }
}
