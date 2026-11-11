import { useRef, useState } from 'react'
import { api } from '../../api'
import { TextArea } from '../../components/Fields'
import { Notice } from '../../components/Feedback'
import { fileData } from '../worlds/loreText'
import { MAKE_TEXT, filledLine, picksOf, withDraft, withMade, type DramatisForm, type Drafted, type MadeForm, type OpenedCard } from './makeText'

interface Props {
  form: MadeForm
  onDraft: (form: MadeForm) => void
  /** With no text model yet, Write it becomes Add a model and opens Settings > Models (SH-3). */
  onAddModel?: () => void
  /** A party member the player makes, not the character they play. */
  party?: boolean
}

/** Above the fields: an idea the story's model drafts the whole character from, or a character the person already
 * has, pasted or opened from a card and split into the fields (adventure/making.py). Nothing is saved. */
export function QuickStart({ form, onDraft, onAddModel, party }: Props) {
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
    const found = await api<{ draft: Drafted }>('/story/make/draft', picksOf(form, idea, party))
    onDraft(withDraft(form, found.draft))
    setFilled('')
  })
  const split = (text: string) => run(async () => {
    const found = await api<{ draft: Drafted; filled_in: string[] }>('/story/make/split', { text, ...(party ? { party } : {}) })
    onDraft(withDraft(form, found.draft))
    setFilled(filledLine(found.filled_in))
    setPasting(false)
  })
  // A Dramatis card fills the form as it was made; any other card's text waits in the box for the split.
  const opened = (card: OpenedCard, made: DramatisForm | null) => {
    onDraft(made ? { ...withMade(form, made), card } : { ...form, card })
    if (!made) return
    setFilled(MAKE_TEXT.fromDramatis(made.name))
    setPasting(false)
  }
  return (
    <div className="make-quick">
      <TextArea label={MAKE_TEXT.idea} value={idea} onChange={setIdea} maxLength={2000} grows placeholder={MAKE_TEXT.ideaPlaceholder} />
      <div className="make-actions">
        {onAddModel
          ? <button type="button" className="button" onClick={onAddModel}>{MAKE_TEXT.addModel}</button>
          : <button type="button" className="button" disabled={busy} onClick={() => void write()}>{busy && !pasting ? MAKE_TEXT.writing : MAKE_TEXT.write}</button>}
        <button type="button" className="button quiet" aria-expanded={pasting} onClick={() => setPasting(!pasting)}>{MAKE_TEXT.paste}</button>
      </div>
      {pasting && <PasteBox busy={busy} disabled={!!onAddModel} onSplit={split} onError={setError} onCard={opened} />}
      {form.card && <CardTicks card={form.card} onChange={(card) => onDraft({ ...form, card })} />}
      {error && <Notice tone="error">{error}</Notice>}
      {filled && <p className="make-filled" role="status">{filled}</p>}
    </div>
  )
}

interface PasteProps { busy: boolean; disabled: boolean; onSplit: (text: string) => void; onError: (text: string) => void; onCard: (card: OpenedCard, made: DramatisForm | null) => void }

type CardFound = Pick<OpenedCard, 'name' | 'book' | 'picture'> & { text: string; form: DramatisForm | null }

/** A character the person already has: pasted, or a card's text opened into the box to read first. */
function PasteBox({ busy, disabled, onSplit, onError, onCard }: PasteProps) {
  const [text, setText] = useState('')
  const picker = useRef<HTMLInputElement>(null)
  const open = async (file: File | undefined) => {
    if (!file) return
    try {
      const data = await fileData(file)
      const found = await api<CardFound>('/story/make/card', { filename: file.name, data })
      setText(found.text)
      // What else it holds is kept by default, for the person to untick.
      onCard({ filename: file.name, data, name: found.name, book: found.book, picture: found.picture, lorebook: true, usePicture: true }, found.form)
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

/** What a card holds besides the character, ticked to keep at Begin: its picture as the portrait, and its lorebook
 * added to the lore. Shown only when the card holds either. */
function CardTicks({ card, onChange }: { card: OpenedCard; onChange: (card: OpenedCard) => void }) {
  if (!card.book && !card.picture) return null
  return (
    <fieldset className="make-card">
      <legend>{MAKE_TEXT.cardOf(card.name)}</legend>
      {card.picture && <img className="make-card-picture" src={card.picture} alt="" />}
      <div className="make-card-ticks">
        {card.picture && <label className="checkbox-row"><input type="checkbox" checked={card.usePicture} onChange={(event) => onChange({ ...card, usePicture: event.target.checked })} />{MAKE_TEXT.usePicture}</label>}
        {card.book && <label className="checkbox-row"><input type="checkbox" checked={card.lorebook} onChange={(event) => onChange({ ...card, lorebook: event.target.checked })} />{MAKE_TEXT.addBook(card.book.name, card.book.entries)}</label>}
      </div>
    </fieldset>
  )
}
