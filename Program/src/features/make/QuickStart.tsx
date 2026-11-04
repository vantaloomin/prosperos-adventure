import { useRef, useState } from 'react'
import { api } from '../../api'
import { TextArea } from '../../components/Fields'
import { Notice } from '../../components/Feedback'
import { fileData } from '../worlds/loreText'
import { MAKE_TEXT, filledLine, picksOf, withDraft, type Drafted, type MadeForm } from './makeText'

interface Props {
  form: MadeForm
  onDraft: (form: MadeForm) => void
  /** With no text model yet, Write it becomes Add a model and opens Settings > Models (SH-3). */
  onAddModel?: () => void
}

/** Above the fields: an idea the story's model drafts the whole character from, or a character the person already
 * has, pasted or opened from a card and split into the fields (adventure/making.py). Nothing is saved. */
export function QuickStart({ form, onDraft, onAddModel }: Props) {
  const [idea, setIdea] = useState('')
  const [pasting, setPasting] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [filled, setFilled] = useState('')
  const run = async (work: () => Promise<void>) => {
    setBusy(true)
    setError('')
    try { await work() } catch (failure) { setError(failure instanceof Error ? failure.message : MAKE_TEXT.failed) } finally { setBusy(false) }
  }
  const write = () => run(async () => {
    const found = await api<{ draft: Drafted }>('/story/make/draft', picksOf(form, idea))
    onDraft(withDraft(form, found.draft))
    setFilled('')
  })
  const split = (text: string) => run(async () => {
    const found = await api<{ draft: Drafted; filled_in: string[] }>('/story/make/split', { text })
    onDraft(withDraft(form, found.draft))
    setFilled(filledLine(found.filled_in))
    setPasting(false)
  })
  return (
    <div className="make-quick">
      <TextArea label={MAKE_TEXT.idea} value={idea} onChange={setIdea} maxLength={2000} grows placeholder={MAKE_TEXT.ideaPlaceholder} />
      <div className="make-actions">
        {onAddModel
          ? <button type="button" className="button" onClick={onAddModel}>{MAKE_TEXT.addModel}</button>
          : <button type="button" className="button" disabled={busy} onClick={() => void write()}>{busy && !pasting ? MAKE_TEXT.writing : MAKE_TEXT.write}</button>}
        <button type="button" className="button quiet" aria-expanded={pasting} onClick={() => setPasting(!pasting)}>{MAKE_TEXT.paste}</button>
      </div>
      {pasting && <PasteBox busy={busy} disabled={!!onAddModel} onSplit={split} onError={setError} />}
      {error && <Notice tone="error">{error}</Notice>}
      {filled && <p className="make-filled" role="status">{filled}</p>}
    </div>
  )
}

interface PasteProps { busy: boolean; disabled: boolean; onSplit: (text: string) => void; onError: (text: string) => void }

/** A character the person already has: pasted, or a card's text opened into the box to read first. */
function PasteBox({ busy, disabled, onSplit, onError }: PasteProps) {
  const [text, setText] = useState('')
  const picker = useRef<HTMLInputElement>(null)
  const open = async (file: File | undefined) => {
    if (!file) return
    try {
      const found = await api<{ text: string }>('/story/make/card', { filename: file.name, data: await fileData(file) })
      setText(found.text)
    } catch (failure) { onError(failure instanceof Error ? failure.message : MAKE_TEXT.failed) }
    if (picker.current) picker.current.value = ''
  }
  return (
    <div className="make-paste">
      <TextArea label={MAKE_TEXT.pasted} value={text} onChange={setText} rows={6} maxLength={40000} />
      <div className="make-actions">
        <button type="button" className="button" disabled={busy || disabled || !text.trim()} onClick={() => onSplit(text)}>{busy ? MAKE_TEXT.splitting : MAKE_TEXT.split}</button>
        <button type="button" className="button quiet" onClick={() => picker.current?.click()}>{MAKE_TEXT.open}</button>
        <input ref={picker} type="file" hidden accept=".png,.json,.charx,.byaf" onChange={(event) => void open(event.target.files?.[0])} />
      </div>
    </div>
  )
}
