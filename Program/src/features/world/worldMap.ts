/** Marinara world maps (dungeon/world/marinara.py), read in the page before they are sent.
 *
 * An export with its artwork can run to hundreds of megabytes, nearly all of it pictures as base64 text that the
 * Dungeon does not import. The file is streamed and every very long string is left empty on the way, so only the
 * map itself (a few hundred kilobytes) is ever held whole, parsed or sent. */

/** Longer than any place's notes, far shorter than a picture. */
export const LONG_STRING = 64 * 1024

/** Whether a file is a world map, from its name or its first few kilobytes. */
export function isWorldMap(name: string, head: string): boolean {
  if (/\.(world|hierarchical)-map\.json$/i.test(name)) return true
  return head.includes('"marinara-hierarchical-map"') || (head.includes('"locations"') && head.includes('"parentId"'))
}

/** JSON text in, the same text out with every string longer than `limit` emptied, one chunk at a time. */
export class LongStringDropper {
  private inString = false
  private escaped = false
  private held: string[] = []
  private heldLength = 0
  private dropping = false
  private readonly limit: number

  constructor(limit = LONG_STRING) { this.limit = limit }

  push(chunk: string): string {
    const out: string[] = []
    let at = 0
    while (at < chunk.length) {
      if (!this.inString) {
        const quote = chunk.indexOf('"', at)
        if (quote < 0) { out.push(chunk.slice(at)); break }
        out.push(chunk.slice(at, quote + 1))
        this.inString = true
        at = quote + 1
        continue
      }
      const end = this.closing(chunk, at)
      if (end < 0) { this.hold(chunk.slice(at)); break }
      this.hold(chunk.slice(at, end))
      out.push(this.release(), '"')
      this.inString = false
      at = end + 1
    }
    return out.join('')
  }

  /** Where the open string ends in this chunk, or -1, keeping track of a backslash split across chunks. */
  private closing(chunk: string, from: number): number {
    let at = from
    if (this.escaped) { this.escaped = false; at += 1 }
    const special = /[\\"]/g
    for (;;) {
      special.lastIndex = at
      const found = special.exec(chunk)
      if (!found) return -1
      if (found[0] === '"') return found.index
      if (found.index + 1 >= chunk.length) { this.escaped = true; return -1 }
      at = found.index + 2
    }
  }

  private hold(text: string) {
    if (this.dropping) return
    this.held.push(text)
    this.heldLength += text.length
    if (this.heldLength > this.limit) { this.dropping = true; this.held = [] }
  }

  private release(): string {
    const text = this.dropping ? '' : this.held.join('')
    this.held = []
    this.heldLength = 0
    this.dropping = false
    return text
  }
}

/** A world map file as JSON, without its pictures, read a piece at a time. */
export async function readWorldMap(file: Blob): Promise<unknown> {
  const reader = file.stream().pipeThrough(new TextDecoderStream()).getReader()
  const dropper = new LongStringDropper()
  const parts: string[] = []
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    parts.push(dropper.push(value))
  }
  try {
    return JSON.parse(parts.join(''))
  } catch {
    throw new Error('This world map is not readable JSON. Export it from Marinara again.')
  }
}
