import assert from 'node:assert/strict'
import { readdirSync } from 'node:fs'
import { join } from 'node:path'
import { test } from 'node:test'

function modules(folder: string): string[] {
  return readdirSync(folder, { withFileTypes: true }).flatMap((entry) =>
    entry.isDirectory() ? modules(join(folder, entry.name)) : [join(folder, entry.name)])
}

// Windows disks ignore case, so an import of `./Feed` can resolve to feed.ts there.
test('no two modules share an import path apart from case', () => {
  const seen = new Map<string, string>()
  for (const path of modules('src')) {
    const key = path.replace(/\.tsx?$/, '').toLowerCase()
    const earlier = seen.get(key)
    assert.equal(earlier, undefined, `${path} and ${earlier} share an import path on Windows`)
    seen.set(key, path)
  }
})
