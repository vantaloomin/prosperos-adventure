import { useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './api'
import type { DebugTime } from './types'
import { syncAppClock } from './appTime.ts'

export const DEBUG_TIME_KEY = ['debug-time']

/** Debug time's state, kept fresh enough for the banner: quickly during a jump, else once a minute. */
export function useDebugTime() {
  const client = useQueryClient()
  const query = useQuery({
    queryKey: DEBUG_TIME_KEY,
    queryFn: async () => { const status = await api<DebugTime>('/debug-time'); syncAppClock(status); return status },
    refetchInterval: (current) => current.state.data?.jumping ? 1000 : 60_000,
  })
  const jumping = !!query.data?.jumping
  const fast = (query.data?.speed ?? 1) > 1
  // Whatever happened in the skipped or sped-up time shows without reopening each view.
  useEffect(() => {
    if (jumping) return undefined
    if (query.data?.active) void client.invalidateQueries({ predicate: (item) => item.queryKey[0] !== DEBUG_TIME_KEY[0] })
    if (!fast) return undefined
    const timer = window.setInterval(() => void client.invalidateQueries({ predicate: (item) => item.queryKey[0] !== DEBUG_TIME_KEY[0] }), 15_000)
    return () => window.clearInterval(timer)
  }, [jumping, fast, query.data?.active, client])
  return query
}
