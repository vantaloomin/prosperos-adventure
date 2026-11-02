import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { Send } from 'lucide-react'
import { AiFooter } from '../../components/Safety'
import type { Awaiting, ReplyKind } from './round'

/** `you` is the user's character's name, empty when they have none yet. */
interface Props { waiting: Awaiting; speaker: string; you: string; busy: boolean; onAnswer: (kind: ReplyKind, text: string) => void }

/** In place of the composer while someone has spoken to the user's character (docs/spec.md "Waiting and pauses"):
 *  the two lines before, who spoke and their line in full, then Reply, Say nothing or Let <name> answer. The last is
 *  an opt-in for this one line only. */
export function ReplyCard({ waiting, speaker, you, busy, onAnswer }: Props) {
  const [text, setText] = useState('')
  const box = useRef<HTMLTextAreaElement>(null)
  useEffect(() => { box.current?.focus() }, [waiting.line])
  const reply = () => { if (text.trim() && !busy) onAnswer('reply', text) }
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); reply() }
  }
  return (<>
    <section className="reply-card" aria-labelledby="reply-card-line">
      {waiting.context.map((line, index) => <p key={index} className="reply-context">{line}</p>)}
      <p className="reply-line" id="reply-card-line"><strong>{speaker}</strong> {waiting.line}</p>
      <form className="reply-form" onSubmit={(event) => { event.preventDefault(); reply() }}>
        <label className="visually-hidden" htmlFor="reply-text">Your reply</label>
        <textarea ref={box} id="reply-text" rows={2} maxLength={2000} value={text} placeholder={you ? `What does ${you} say?` : 'What do you say?'}
          onChange={(event) => setText(event.target.value)} onKeyDown={onKeyDown} />
        <div className="reply-actions">
          <button type="button" className="button" disabled={busy} onClick={() => onAnswer('silent', '')}>Say nothing</button>
          <button type="button" className="button" disabled={busy} onClick={() => onAnswer('let_answer', '')}>{you ? `Let ${you} answer` : 'Let your character answer'}</button>
          <button type="submit" className="button primary" disabled={busy || !text.trim()}><Send aria-hidden="true" />Reply</button>
        </div>
      </form>
    </section>
    <AiFooter />
  </>)
}
