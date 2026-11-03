import assert from 'node:assert/strict'
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { test } from 'node:test'

// Boxes the user types into never get the browser's past entries: React's ids repeat across screens, so the browser
// offers words typed into some other box (Prospero's Companion #433).
const NOT_TYPED = /type="(range|file|checkbox|radio|color|number|datetime-local|date|time|hidden)"/

function sources(folder: string): string[] {
  return readdirSync(folder, { withFileTypes: true }).flatMap((entry) => {
    const path = join(folder, entry.name)
    return entry.isDirectory() ? sources(path) : path.endsWith('.tsx') ? [path] : []
  })
}

test('every text box turns the browser’s past entries off', () => {
  const missing: string[] = []
  for (const path of sources('src')) {
    const text = readFileSync(path, 'utf8')
    for (const found of text.matchAll(/<input\b[\s\S]*?\/>/g)) {
      const tag = found[0]
      if (!NOT_TYPED.test(tag) && !tag.includes('autoComplete')) missing.push(`${path}: ${tag.slice(0, 80)}`)
    }
  }
  assert.deepEqual(missing, [])
})
