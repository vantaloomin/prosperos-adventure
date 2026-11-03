import { Fragment, type ReactNode } from 'react'
import { inlineRuns, type Mark, type Run } from './inline'

/** Plain runs as they are; `words` can turn a plain run into more (the story links names in it). */
type Words = (text: string) => ReactNode

function marked(run: Run, words?: Words): ReactNode {
  return run.marks.reduceRight<ReactNode>((inside, mark: Mark) => {
    if (mark === 'em') return <em>{inside}</em>
    if (mark === 'strong') return <strong>{inside}</strong>
    if (mark === 'del') return <del>{inside}</del>
    return <code>{inside}</code>
  }, run.marks.includes('code') || !words ? run.text : words(run.text))
}

/** Runs already cut (./inline.ts runsBetween), with their italics, bold, strikes and code. */
export function Runs({ runs, words }: { runs: Run[]; words?: Words }) {
  return <>{runs.map((run, index) => <Fragment key={index}>{marked(run, words)}</Fragment>)}</>
}

/** Model text with its inline Markdown shown as styling, never as asterisks. React escapes every run, so markup in
 *  the text stays text. */
export function InlineText({ text, words }: { text: string; words?: Words }) {
  return <Runs runs={inlineRuns(text)} words={words} />
}
