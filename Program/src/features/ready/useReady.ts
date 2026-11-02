import { useEffect, useMemo } from 'react'
import { useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'
import { api } from '../../api'
import { isRunning, type ReadyView } from './readyText'

export const READY_KEY = ['ready']
// Undo after Cancel lasts 10 seconds, then the part file goes; kept here so leaving the screen doesn't keep it.
const UNDO_MS = 10_000
let discardTimer: number | undefined

const polling = (view?: ReadyView) => isRunning(view)

/** "Set it up for me" as it stands; checked every second while it downloads. */
export function useReady(enabled = true) {
  const client = useQueryClient()
  const query = useQuery({ queryKey: READY_KEY, queryFn: () => api<ReadyView>('/ready'), enabled,
    refetchInterval: (query) => polling(query.state.data) ? 1000 : false })
  const ready = query.data?.status === 'ready'
  // When the download finishes in the background, everything that asks "is a model connected?" asks again.
  useEffect(() => {
    if (!ready) return
    void client.invalidateQueries({ queryKey: ['connection'] })
    void client.invalidateQueries({ queryKey: ['models'] })
  }, [ready, client])
  return query
}

function refresh(client: QueryClient, view: ReadyView) {
  client.setQueryData(READY_KEY, view)
  if (view.status === 'ready') {
    void client.invalidateQueries({ queryKey: ['connection'] })
    void client.invalidateQueries({ queryKey: ['models'] })
  }
  return view
}

export function useReadyActions() {
  const client = useQueryClient()
  return useMemo(() => actions(client), [client])
}

function actions(client: QueryClient) {
  const send = async (path: string, body?: unknown, method?: string) => refresh(client, await api<ReadyView>(path, body, method))
  return {
    start: (model: string) => { window.clearTimeout(discardTimer); return send('/ready', { model }) },
    pause: () => send('/ready/pause', {}),
    cancel: async () => {
      const view = await send('/ready/cancel', {})
      window.clearTimeout(discardTimer)
      discardTimer = window.setTimeout(() => { void send('/ready', undefined, 'DELETE') }, UNDO_MS)
      return view
    },
    use: () => send('/ready/use', {}),
    seen: (what: 'notice' | 'settings') => send('/ready/seen', { what }),
  }
}

