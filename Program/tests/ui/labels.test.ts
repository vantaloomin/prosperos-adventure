import assert from 'node:assert/strict'
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { test } from 'node:test'

function components(folder: string): string[] {
  return readdirSync(folder, { withFileTypes: true }).flatMap((entry) =>
    entry.isDirectory() ? components(join(folder, entry.name)) : entry.name.endsWith('.tsx') ? [join(folder, entry.name)] : [])
}

/** The text of a JSX opening tag starting at `start`, skipping `>` inside `{…}` and quotes. */
function openingTag(source: string, start: number): string {
  let depth = 0
  let quote = ''
  for (let index = start; index < source.length; index += 1) {
    const char = source[index]
    if (quote) quote = char === quote ? '' : quote
    else if ('"\'`'.includes(char)) quote = char
    else depth += char === '{' ? 1 : char === '}' ? -1 : 0
    if (!quote && depth === 0 && char === '>') return source.slice(start, index + 1)
  }
  return source.slice(start)
}

function line(source: string, index: number) { return source.slice(0, index).split('\n').length }

/** Inside an open <label>…</label> at this point of the file. */
function wrappedInLabel(source: string, index: number) {
  const before = source.slice(0, index)
  return before.lastIndexOf('<label') > before.lastIndexOf('</label>')
}

function unlabelledControls(path: string): string[] {
  const source = readFileSync(path, 'utf8')
  const problems: string[] = []
  for (const match of source.matchAll(/<(input|select|textarea)\b/g)) {
    const tag = openingTag(source, match.index)
    if (/type="hidden"|\shidden[\s/>]/.test(tag)) continue
    const named = /\baria-label(ledby)?=/.test(tag) || /\{\.\.\./.test(tag)
    // An id only names the control when a <label htmlFor> or a <Field> in the same file points at it.
    const linked = /\bid=/.test(tag) && /htmlFor=|<Field\b/.test(source)
    if (!named && !linked && !wrappedInLabel(source, match.index)) problems.push(`${path}:${line(source, match.index)} <${match[1]}> has no label`)
  }
  return problems
}

/** Buttons whose only content is icons (or nothing) need a name of their own. */
function namelessButtons(path: string): string[] {
  const source = readFileSync(path, 'utf8')
  const problems: string[] = []
  for (const match of source.matchAll(/<button\b/g)) {
    const tag = openingTag(source, match.index)
    if (/\baria-label(ledby)?=/.test(tag) || /\{\.\.\./.test(tag)) continue
    const end = source.indexOf('</button>', match.index + tag.length)
    if (tag.endsWith('/>') || end < 0) { problems.push(`${path}:${line(source, match.index)} <button> has no content`); continue }
    const body = source.slice(match.index + tag.length, end)
    const iconsOnly = body.replace(/<[A-Z]\w*\b[^>]*\/>/g, '').trim() === ''
    if (iconsOnly) problems.push(`${path}:${line(source, match.index)} icon-only <button> has no aria-label`)
  }
  return problems
}

test('every input, select and textarea has a label', () => {
  assert.deepEqual(components('src').flatMap(unlabelledControls), [])
})

test('every icon-only button has a name', () => {
  assert.deepEqual(components('src').flatMap(namelessButtons), [])
})
