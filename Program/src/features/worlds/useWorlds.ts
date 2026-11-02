import { useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, openedIn } from '../../api'
import type { Worlds } from '../../types'

export const WORLDS_KEY = ['worlds']

/** Every persona and their worlds. Checked now and then, so a switch made on the phone (or the PC) reloads the other. */
export function useWorlds() {
  return useQuery({ queryKey: WORLDS_KEY, queryFn: () => api<Worlds>('/worlds'), refetchInterval: 30_000 })
}

/** Everything on screen belongs to one world, so arriving in another starts the page afresh in the chat. */
export function enter() {
  window.location.hash = '#conversation'
  window.location.reload()
}

/** Reload when the active world changed somewhere else since this page opened. */
export function useFollowWorld() {
  const worlds = useWorlds()
  const opened = useRef<string | null>(null)
  const active = worlds.data?.active_world_id
  useEffect(() => {
    if (!active) return
    if (opened.current === null) { opened.current = active; openedIn(active) }
    else if (opened.current !== active) enter()
  }, [active])
  return worlds
}
