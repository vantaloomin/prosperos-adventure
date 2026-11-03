import { useState } from 'react'
import { Eye } from 'lucide-react'
import type { LineMarks } from './round'
import { MARK_NAMES } from './roundText'
import { TurnReport } from './TurnReport'

/** Under a line of a round turn: a mark when the GM view was open on it (PL-12), and its report, opened in place.
 *  Nothing for a line with no turn, or while nobody at the table thinks (`marks` null). */
export function LineTools({ turnId, marks }: { turnId?: string | null; marks?: LineMarks | null }) {
  const [open, setOpen] = useState(false)
  if (!marks || !turnId) return null
  return (<>
    {marks.marked.includes(turnId) && <span className="line-mark" title={MARK_NAMES.gm}><Eye aria-hidden="true" /><span className="visually-hidden">{MARK_NAMES.gm}</span></span>}
    <button type="button" className="text-button line-report" aria-expanded={open} onClick={() => setOpen(!open)}>{MARK_NAMES.report}</button>
    {open && <TurnReport turnId={turnId} table={marks.table} />}
  </>)
}
