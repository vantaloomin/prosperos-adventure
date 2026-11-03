import { Fragment, useEffect, useRef, useState, type ReactNode } from 'react'
import { PenLine, Repeat } from 'lucide-react'
import type { StoryMessage } from '../../types'
import { InfoTip } from '../../components/InfoTip'
import { inlineRuns, isBreak, plainText, runsBetween } from '../../components/inline'
import { Runs } from '../../components/InlineText'
import { reworded, sentences, wordsOf } from './storyText'
import { linkText } from './entity'
import { EntityName } from './EntityCard'
import { useNameLinks } from './entityContext'
import { IllustrateButton } from './StoryArt'

interface Props {
  message: StoryMessage
  /** Rewrite a passage in new words, with an optional note; the dice and the record's facts stay (adventure/passages.py). */
  onRewrite?: (id: string, passage: string, note: string) => Promise<void>
  /** Switch between the wording before the last rewrite and the rewrite. */
  onSwitch?: (id: string) => Promise<void>
  /** The narration as it streamed, for the turn just told: sentences the checks reworded since are marked. */
  draft?: string
}

/** Where the Rewrite chip sits in the narration box: just under the end of the selected range. */
function chipAt(range: Range, box: HTMLElement): { top: number; left: number } {
  const end = range.getBoundingClientRect?.()
  if (!end) return { top: 0, left: 0 }
  const frame = box.getBoundingClientRect()
  return { top: end.bottom - frame.top + 4, left: Math.max(0, end.right - frame.left - 80) }
}

const REWORDED = 'The prose and continuity checks reworded the marked sentences after they were written. The dice and what happened are the same.'

const rewordedIn = (text: string, draft?: string) => new Set(draft ? [...reworded(draft, text)].map(wordsOf) : [])

/** Plain text with the names of people met and factions known as links to their cards (rule 2). */
function useLinkedWords(): (text: string) => ReactNode {
  const links = useNameLinks()
  return (text) => linkText(text, links).map((part, index) => typeof part === 'string' ? part : <EntityName key={index} entity={part.entity}>{part.name}</EntityName>)
}

/** A paragraph, its Markdown italics and bold shown as such, with the sentences in `changed` (their words, as
 *  ./storyText.ts wordsOf gives them) marked; the mark fades in so the swap reads as an edit. */
function Paragraph({ text, changed }: { text: string; changed: Set<string> }) {
  const words = useLinkedWords()
  if (isBreak(text)) return <hr className="story-break" />
  const runs = inlineRuns(text)
  if (!changed.size) return <p><Runs runs={runs} words={words} /></p>
  const plain = runs.map((run) => run.text).join('')
  const cut = sentences(plain)
  const starts: number[] = []
  for (const sentence of cut) starts.push(plain.indexOf(sentence, starts.length ? starts[starts.length - 1] + cut[starts.length - 1].length : 0))
  return <p>{cut.map((sentence, index) => {
    const part = <Runs runs={runsBetween(runs, starts[index], starts[index] + sentence.length)} words={words} />
    return changed.has(wordsOf(sentence)) ? <mark key={index} className="story-reworded">{part}</mark> : <Fragment key={index}>{part}</Fragment>
  })}</p>
}

const shortened = (passage: string) => { const text = plainText(passage); return text.length > 120 ? `${text.slice(0, 117).trimEnd()}…` : text }

/** A narration: its flagged paragraphs marked with why and a Rewrite button. Selecting a passage shows a small
 *  Rewrite chip beside it, and only the chip opens the form, so selecting text to copy it costs nothing. */
export function StoryNarration({ message, onRewrite, onSwitch, draft }: Props) {
  const box = useRef<HTMLDivElement>(null)
  const [chosen, setChosen] = useState('')
  // A selected passage, and where its chip sits inside the narration box.
  const [offer, setOffer] = useState<{ text: string; top: number; left: number } | null>(null)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const form = useRef<HTMLFormElement>(null)
  useEffect(() => { if (chosen) form.current?.scrollIntoView?.({ block: 'nearest' }) }, [chosen])
  useEffect(() => {
    if (!offer) return
    // The chip goes when the selection does (a click elsewhere, a new selection outside this narration).
    const gone = () => { if (!window.getSelection()?.toString().trim()) setOffer(null) }
    document.addEventListener('selectionchange', gone)
    return () => document.removeEventListener('selectionchange', gone)
  }, [offer])
  const changed = rewordedIn(message.text, draft)
  const flags = new Map((message.flags ?? []).map((flag) => [flag.passage, flag.why]))
  const pick = () => {
    const selection = window.getSelection()
    const text = selection?.toString().trim() ?? ''
    if (!onRewrite || !text || !selection?.anchorNode || !box.current?.contains(selection.anchorNode) || !selection.rangeCount) return
    setOffer({ text, ...chipAt(selection.getRangeAt(0), box.current) })
  }
  const act = async (work: () => Promise<void>) => {
    setBusy(true)
    try { await work(); setChosen(''); setNote('') } finally { setBusy(false) }
  }
  return (<>
    <div className="story-narration" ref={box} onMouseUp={pick} onKeyUp={pick} onTouchEnd={pick}>
      {message.text.split(/\n{2,}/).map((part, index) => {
        const why = flags.get(part.trim())
        if (!why) return <Paragraph key={index} text={part} changed={changed} />
        return (
          <div key={index} className="story-flagged">
            <Paragraph text={part} changed={changed} />
            {onRewrite && <span className="story-flag">
              <InfoTip id={`flag-${message.id}-${index}`} label="why this passage is marked" text={why.join(' ')} />
              <button type="button" className="text-button" onClick={() => setChosen(part.trim())}><PenLine aria-hidden="true" />Rewrite</button>
            </span>}
          </div>)
      })}
      {offer && onRewrite && <button type="button" className="button story-rewrite-chip" style={{ top: offer.top, left: offer.left }}
        onMouseDown={(event) => event.preventDefault()} onClick={() => { setChosen(offer.text); setOffer(null) }}>
        <PenLine aria-hidden="true" />Rewrite</button>}
    </div>
    {!!changed.size && <p className="story-reworded-note subtle">Reworded after writing <InfoTip id={`reworded-${message.id}`} label="the marked sentences" text={REWORDED} /></p>}
    {chosen && onRewrite && <form ref={form} className="story-rewrite" onSubmit={(event) => { event.preventDefault(); void act(() => onRewrite(message.id, chosen, note)) }}>
      <p className="subtle">Rewrite &ldquo;{shortened(chosen)}&rdquo; in new words. The dice and what happened stay the same.</p>
      <label>What to change (optional)
        <input autoComplete="off" value={note} maxLength={300} placeholder="Less purple, she wouldn't say that…" onChange={(event) => setNote(event.target.value)} />
      </label>
      <div className="form-actions">
        <button type="submit" className="button primary" disabled={busy}><PenLine aria-hidden="true" />{busy ? 'Rewriting…' : 'Rewrite'}</button>
        <button type="button" className="text-button" disabled={busy} onClick={() => setChosen('')}>Cancel</button>
      </div>
    </form>}
    <NarrationActions message={message} busy={busy} illustrate={!!onRewrite && !draft} onSwitch={onSwitch && (() => void act(() => onSwitch(message.id)))} />
  </>)
}

/** Under a passage: switch back to its earlier wording after a rewrite, and picture it. */
function NarrationActions({ message, busy, illustrate, onSwitch }: { message: StoryMessage; busy: boolean; illustrate: boolean; onSwitch?: () => void }) {
  return <>
    {message.previous && onSwitch && <button type="button" className="text-button story-back" disabled={busy} onClick={onSwitch}
      title="Switch between the wording before your last rewrite and the rewrite."><Repeat aria-hidden="true" />Switch wording</button>}
    {illustrate && <IllustrateButton messageId={message.id} />}
  </>
}
