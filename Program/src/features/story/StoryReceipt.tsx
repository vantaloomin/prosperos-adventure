import { Bandage, BookOpen, Coins, HeartCrack, Package, ScrollText } from 'lucide-react'
import type { ReceiptChip } from '../../types'
import { askForDrawer, WIDGET_NAMES, type Widget } from './scene'

const ICONS = { coins: Coins, item: Package, hurt: HeartCrack, injury: Bandage, quest: ScrollText, learned: BookOpen }
/** The widget each chip opens (rule 5: each chip opens its widget). */
const OPENS: Record<ReceiptChip['kind'], Widget> = { coins: 'pack', item: 'pack', hurt: 'sheet', injury: 'sheet', quest: 'journal', learned: 'journal' }

/** The turn receipt (dungeon/receipt.py): what the turn changed, in chips under its narration; each opens the widget
 *  where it shows (the pack, the sheet, the journal) in the side panel. */
export function TurnReceipt({ chips }: { chips?: ReceiptChip[] }) {
  if (!chips?.length) return null
  return (
    <ul className="turn-receipt" aria-label="What changed this turn">
      {chips.map((chip, index) => {
        const Icon = ICONS[chip.kind]
        const opens = OPENS[chip.kind]
        return <li key={index}>
          <button type="button" className={`receipt-chip ${chip.tone}`} onClick={() => askForDrawer(opens)} title={`Open ${WIDGET_NAMES[opens].toLowerCase()}`}>
            <Icon aria-hidden="true" />{chip.text}</button>
        </li>
      })}
    </ul>
  )
}
