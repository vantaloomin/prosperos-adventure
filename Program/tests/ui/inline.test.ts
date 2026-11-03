import assert from 'node:assert/strict'
import { test } from 'node:test'
import { inlineRuns, isBreak, plainText, runsBetween } from '../../src/components/inline.ts'

const shown = (text: string) => inlineRuns(text).map((run) => run.marks.length ? `<${run.marks.join('+')}>${run.text}` : run.text)

test('italics and bold come out as marked runs, without their markers', () => {
  assert.deepEqual(shown('for Michael alone: "*Mea lux, observa.* Tell me."'), ['for Michael alone: "', '<em>Mea lux, observa.', ' Tell me."'])
  assert.deepEqual(shown('She was **very** sure, _quite_ sure.'), ['She was ', '<strong>very', ' sure, ', '<em>quite', ' sure.'])
  assert.deepEqual(shown('__Stop.__ ***Now.***'), ['<strong>Stop.', ' ', '<strong+em>Now.'])
  assert.deepEqual(shown('~~Gone~~ and `ls -la`'), ['<del>Gone', ' and ', '<code>ls -la'])
})

test('marks nest', () => {
  assert.deepEqual(shown('*a **b** c*'), ['<em>a ', '<em+strong>b', '<em> c'])
  assert.deepEqual(shown('**bold *both***'), ['<strong>bold ', '<strong+em>both'])
  assert.deepEqual(shown('*ital **both***'), ['<em>ital ', '<em+strong>both'])
})

test('a marker with no partner, or no word beside it, stays as typed', () => {
  assert.deepEqual(shown('2 * 3 * 4'), ['2 * 3 * 4'])
  assert.deepEqual(shown('my_snake_case name'), ['my_snake_case name'])
  assert.deepEqual(shown('* not a list item'), ['* not a list item'])
  // A stream that has not closed its italics yet.
  assert.deepEqual(shown('He said, *Mea lux'), ['He said, *Mea lux'])
  assert.deepEqual(shown('** spaced **'), ['** spaced **'])
  assert.deepEqual(shown('\\*not italic\\*'), ['*not italic*'])
})

test('markup in the text stays text: the runs are plain strings React escapes', () => {
  assert.deepEqual(shown('*<b onmouseover="x">hi</b>*'), ['<em><b onmouseover="x">hi</b>'])
  assert.equal(plainText('<script>alert(1)</script>'), '<script>alert(1)</script>')
})

test('code keeps its asterisks', () => {
  assert.deepEqual(shown('`*a*` and *b*'), ['<code>*a*', ' and ', '<em>b'])
})

test('plain text and cutting runs by their plain text', () => {
  assert.equal(plainText('A *quiet* **room**.'), 'A quiet room.')
  const runs = inlineRuns('One *two three* four')
  assert.deepEqual(runsBetween(runs, 4, 12), [{ text: 'two three'.slice(0, 8), marks: ['em'] }])
  assert.deepEqual(runsBetween(runs, 0, 6), [{ text: 'One ', marks: [] }, { text: 'tw', marks: ['em'] }])
})

test('scene breaks', () => {
  for (const line of ['***', '---', '* * *', ' ___ ']) assert.ok(isBreak(line), line)
  for (const line of ['**', '*a*', '- item']) assert.ok(!isBreak(line), line)
})
