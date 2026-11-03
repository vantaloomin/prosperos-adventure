/** Shared Sidebar Assistant state: whether it is open, a passage the user pointed it at, and its conversation, which
 * lasts while the app is open, is never stored and never reaches the narrator. */
import { useSyncExternalStore } from 'react'
import type { Turn } from './proposals.ts'

export interface Focus { id: string; text: string }
export interface AssistantState<T> { open: boolean; focus: Focus | null; turns: T[] }

const OPEN_KEY = 'adventure:assistant'

function readOpen(): boolean {
  try { return localStorage.getItem(OPEN_KEY) === 'open' } catch { return false }
}

/** A tiny store with no React in it, so it can be tested and shared by the nav, the menu and the panel. */
export function createStore<T>(open = readOpen()) {
  let state: AssistantState<T> = { open, focus: null, turns: [] }
  const listeners = new Set<() => void>()
  const set = (change: Partial<AssistantState<T>>) => {
    state = { ...state, ...change }
    listeners.forEach((listener) => listener())
  }
  const store = {
    get: () => state,
    subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener) } },
    setOpen(next: boolean) {
      set({ open: next, ...(next ? {} : { focus: null }) })
      try { localStorage.setItem(OPEN_KEY, next ? 'open' : 'closed') } catch { /* A blocked store only forgets the choice. */ }
    },
    toggle() { store.setOpen(!state.open) },
    /** Open it on one of the narrator's passages. */
    ask(focus: Focus) { set({ focus: { id: focus.id, text: focus.text } }); store.setOpen(true) },
    clearFocus() { set({ focus: null }) },
    setTurns(turns: T[]) { set({ turns }) },
  }
  return store
}

export const assistant = createStore<Turn>()

export function useAssistant(): AssistantState<Turn> {
  return useSyncExternalStore(assistant.subscribe, assistant.get, assistant.get)
}

/** Only whether it is open, for the app shell and the nav. */
export function useAssistantOpen(): boolean {
  const open = () => assistant.get().open
  return useSyncExternalStore(assistant.subscribe, open, open)
}
