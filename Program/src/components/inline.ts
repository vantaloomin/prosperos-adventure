/** Inline Markdown in model text: *em*, _em_, **strong**, __strong__, ***both***, ~~struck~~ and `code`. React-free,
 *  so it is tested on its own (tests/ui/inline.test.ts); ./InlineText.tsx renders the runs. Nothing here makes HTML:
 *  the runs are plain strings that React escapes. A marker with no partner stays as typed, so "2 * 3" and snake_case
 *  read as written, and a stream that has not closed its italics yet shows the asterisk until it does. */

export type Mark = 'em' | 'strong' | 'del' | 'code'
export interface Run { text: string; marks: Mark[] }

const WORD = /[\p{L}\p{N}]/u
const SPACE = /\s/u
const ESCAPABLE = new Set(['*', '_', '~', '`', '\\'])

const runOf = (text: string, at: number, char: string) => {
  let length = 0
  while (text[at + length] === char) length++
  return length
}

/** A marker can open when text follows it, and an underscore not in the middle of a word. */
function opens(text: string, at: number, length: number): boolean {
  const after = text[at + length]
  if (!after || SPACE.test(after)) return false
  return !(text[at] === '_' && at > 0 && WORD.test(text[at - 1]))
}

/** A marker can close when text comes before it, and an underscore not in the middle of a word. */
function closes(text: string, at: number, length: number): boolean {
  const before = text[at - 1]
  if (!before || SPACE.test(before)) return false
  return !(text[at] === '_' && WORD.test(text[at + length] ?? ''))
}

/** Where the content of a `length`-long run of `char` opened at `from` ends, and where its closer ends; null when it
 *  never closes. A run of three closes a shorter opener from its far end: "**bold *both***". */
function closer(text: string, from: number, char: string, length: number): [number, number] | null {
  for (let at = from; at < text.length;) {
    const past = skipped(text, at, char)
    if (past) { at = past; continue }
    const run = runOf(text, at, char)
    if (!run) { at++; continue }
    if (at > from && (run === length || (run === 3 && char !== '`')) && closes(text, at, run)) return [at + run - length, at + run]
    at += run
  }
  return null
}

/** Past an escaped character, or a code span when looking for anything but code's own closer; 0 when neither. */
function skipped(text: string, at: number, char: string): number {
  if (text[at] === '\\') return at + 2
  const end = text[at] === '`' && char !== '`' ? text.indexOf('`', at + 1) : -1
  return end > 0 ? end + 1 : 0
}

const MARKS: Record<string, Record<number, Mark[]>> = {
  '*': { 1: ['em'], 2: ['strong'], 3: ['strong', 'em'] },
  '_': { 1: ['em'], 2: ['strong'], 3: ['strong', 'em'] },
  '~': { 2: ['del'] },
  '`': { 1: ['code'] },
}

function parse(text: string, marks: Mark[], out: Run[]): void {
  let plain = ''
  const flush = () => { if (plain) out.push({ text: plain, marks }); plain = '' }
  for (let at = 0; at < text.length;) {
    const char = text[at]
    if (char === '\\' && ESCAPABLE.has(text[at + 1])) { plain += text[at + 1]; at += 2; continue }
    const kinds = MARKS[char]
    if (!kinds) { plain += char; at++; continue }
    const run = runOf(text, at, char)
    const found = [3, 2, 1].filter((length) => length <= run && kinds[length]).map((length) => {
      const start = at + run - length
      if (!opens(text, start, length)) return null
      const end = closer(text, start + length, char, length)
      return end && { start, length, end }
    }).find(Boolean)
    if (!found) { plain += text.slice(at, at + run); at += run; continue }
    plain += text.slice(at, found.start)
    flush()
    const inner = text.slice(found.start + found.length, found.end[0])
    const wrapped = [...marks, ...kinds[found.length].filter((mark) => !marks.includes(mark))]
    if (char === '`') out.push({ text: inner, marks: wrapped })
    else parse(inner, wrapped, out)
    at = found.end[1]
  }
  flush()
}

const same = (one: Mark[], other: Mark[]) => one.length === other.length && one.every((mark) => other.includes(mark))

/** The text as runs of plain text, each with the marks on it, neighbors with the same marks joined. */
export function inlineRuns(text: string): Run[] {
  const runs: Run[] = []
  parse(text, [], runs)
  return runs.reduce<Run[]>((joined, run) => {
    const last = joined[joined.length - 1]
    if (last && same(last.marks, run.marks)) last.text += run.text
    else joined.push({ ...run })
    return joined
  }, [])
}

/** The text as it reads, with the markers taken out: for labels, quotes and comparisons. */
export const plainText = (text: string) => inlineRuns(text).map((run) => run.text).join('')

/** The runs between two places in their plain text, cut where the places fall inside a run. */
export function runsBetween(runs: Run[], start: number, end: number): Run[] {
  const found: Run[] = []
  let at = 0
  for (const run of runs) {
    const from = Math.max(start, at), to = Math.min(end, at + run.text.length)
    if (from < to) found.push({ text: run.text.slice(from - at, to - at), marks: run.marks })
    at += run.text.length
  }
  return found
}

/** A paragraph standing alone as a scene break: "***", "---", "* * *". */
export const isBreak = (paragraph: string) => /^\s*([*\-_])(?:\s*\1){2,}\s*$/.test(paragraph)
