import { useState } from 'react'
import { Plus } from 'lucide-react'

/** One line of text and Add, cleared once saved; the beat board's new beat and the nudge box's wish. */
interface Props { label: string; placeholder: string; autoFocus?: boolean; onAdd: (text: string) => Promise<boolean> }

export function AddLine({ label, placeholder, autoFocus = false, onAdd }: Props) {
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const add = async () => {
    if (!text.trim() || busy) return
    setBusy(true)
    if (await onAdd(text.trim())) setText('')
    setBusy(false)
  }
  return <form className="add-line" onSubmit={(event) => { event.preventDefault(); void add() }}>
    <input autoComplete="off" aria-label={label} autoFocus={autoFocus} placeholder={placeholder} value={text} maxLength={300} onChange={(event) => setText(event.target.value)} />
    <button type="submit" className="icon-button" aria-label="Add" disabled={!text.trim() || busy}><Plus aria-hidden="true" /></button>
  </form>
}
