// Request helper adapted from prosperos-study src/api.ts at bbcbde4: the Dungeon's client header and error codes.
import { ndjsonLines } from './ndjson.ts'

export class ApiError extends Error {
  constructor(message: string, public status: number, public code?: string) { super(message) }
}

function errorMessage(status: number, data: { detail?: unknown }): string {
  if (typeof data.detail === 'string') return data.detail
  if (Array.isArray(data.detail)) return data.detail.map((item) => item.msg).join('; ')
  return `The Dungeon could not finish that (error ${status}). Please try again.`
}

let world: string | null = null

/** The world this page shows (src/features/worlds/useWorlds.ts). Sent with every request, so a page left open in
 * one world never changes another the PC or phone has since moved to (dungeon/main.py stay_in_world). */
export function openedIn(id: string) { world = id }

function headers(type: string): Record<string, string> {
  return { 'Content-Type': type, 'X-Dungeon-Client': 'workspace', ...(world ? { 'X-Dungeon-World': world } : {}) }
}

export async function api<T>(path: string, body?: unknown, method?: string): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api${path}`, {
      method: method ?? (body === undefined ? 'GET' : 'POST'),
      headers: headers('application/json'),
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError('Cannot reach the Dungeon. Check that it is still running.', 0, 'offline')
  }
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw failure(response.status, data)
  return data as T
}

/** A file sent as the request's whole body, such as a campaign file (dungeon/legacy.py). */
export async function upload<T>(path: string, file: Blob): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api${path}`, { method: 'POST', headers: headers(file.type || 'application/octet-stream'), body: file })
  } catch {
    throw new ApiError('Cannot reach the Dungeon. Check that it is still running.', 0, 'offline')
  }
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw failure(response.status, data)
  return data as T
}

/** A workspace switched in another tab reloads this one on the story. */
function failure(status: number, data: { detail?: unknown; code?: string }): ApiError {
  if (data.code === 'world_changed') { window.location.hash = '#story'; window.location.reload() }
  return new ApiError(errorMessage(status, data), status, data.code)
}

type StreamEvent<T> = { text?: string; done?: T; error?: string; code?: string; status?: number }
/** Anything else a stream sends, such as a turn's stages and rolls (dungeon/story.py answer). */
export type StreamNote = Record<string, unknown>

/** A POST whose answer streams as newline-delimited JSON (dungeon/story_routes.py streamed): `onText` gets each
 * piece as it comes, `onNote` every other event, and the promise resolves with the "done" result. */
export async function streamApi<T>(path: string, body: unknown, onText: (piece: string) => void,
  onNote?: (note: StreamNote) => void): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api${path}`, { method: 'POST', headers: headers('application/json'), body: JSON.stringify(body) })
  } catch {
    throw new ApiError('Cannot reach the Dungeon. Check that it is still running.', 0, 'offline')
  }
  if (!response.ok || !response.body) throw failure(response.status, await response.json().catch(() => ({})))
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    const [events, rest] = ndjsonLines(buffer + value)
    buffer = rest
    const result = handled(events as StreamEvent<T>[], onText, onNote)
    // The turn's after-work (fact extraction) carries on server-side; the reply is ready now.
    if (result !== undefined) { void reader.cancel().catch(() => undefined); return result }
  }
  throw new ApiError('The story stopped before the reply was saved. Try again.', 0, 'stream')
}

/** Passes on streamed text, throws a streamed error, and gives back the result once it comes. */
function handled<T>(events: StreamEvent<T>[], onText: (piece: string) => void, onNote?: (note: StreamNote) => void): T | undefined {
  for (const event of events) {
    if (event.text) onText(event.text)
    if (onNote && !('text' in event || 'done' in event || 'error' in event)) onNote(event as StreamNote)
    if (event.error) throw failure(event.status ?? 500, { detail: event.error, code: event.code })
    if (event.done) return event.done
  }
  return undefined
}

export { newId } from './ids.ts'

