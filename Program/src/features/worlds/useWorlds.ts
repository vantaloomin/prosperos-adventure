import { useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, openedIn } from '../../api'
import type { Worlds } from '../../types'
import { followed } from './arrival'

export const WORLDS_KEY = ['worlds']

/** Every persona and their worlds. Checked now and then, so a switch made on the phone (or the PC) reloads the other. */
export function useWorlds() {
  return useQuery({ queryKey: WORLDS_KEY, queryFn: () => api<Worlds>('/worlds'), refetchInterval: 30_000 })
}

// Other tabs of this browser hear of a switch at once, rather than at their next check (Prospero's Companion #431).
const CHANNEL = 'adventure:worlds'

function tellOtherTabs() {
  try {
    const channel = new BroadcastChannel(CHANNEL)
    channel.postMessage('switched')
    channel.close()
  } catch { /* They follow at their next check. */ }
}

/** Everything on screen belongs to one world, so arriving in another starts the page afresh on the story. */
export function enter() {
  tellOtherTabs()
  window.location.hash = '#story'
  window.location.reload()
}

/** Reload when the active world changed somewhere else since this page opened, saying so once it has. */
export function useFollowWorld() {
  const worlds = useWorlds()
  const opened = useRef<string | null>(null)
  const active = worlds.data?.active_world_id
  const name = worlds.data?.world.name
  const refetch = worlds.refetch
  useEffect(() => {
    if (!active) return
    if (opened.current === null) { opened.current = active; openedIn(active) }
    else if (opened.current !== active) { followed(name); enter() }
  }, [active, name])
  useEffect(() => {
    let channel: BroadcastChannel | null = null
    try { channel = new BroadcastChannel(CHANNEL) } catch { return }
    channel.onmessage = () => { void refetch() }
    return () => channel?.close()
  }, [refetch])
  return worlds
}
