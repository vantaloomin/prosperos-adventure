import { useState } from 'react'
import type { LifeCardShown } from '../../types'

const TONES = { good: 'A good turn', bad: 'A bad turn', grey: 'A mixed turn' }

/** A Life Card the world drew on this line (dungeon/happenings.py with_cards): its picture, title and tone, never
 *  its hidden truth. The picture grows on a click; a veiled card shows only the world's card back. */
export function LifeCard({ card }: { card: LifeCardShown }) {
  const [open, setOpen] = useState(false)
  const label = card.veiled ? 'A veiled Life Card' : `Life Card: ${card.title}`
  return (
    <div className={`life-card tone-${card.tone}${open ? ' open' : ''}`} aria-label={label}>
      {card.art && <button type="button" className="life-card-art" onClick={() => setOpen(!open)}
        title={open ? 'Show smaller' : 'Show larger'} aria-expanded={open}>
        <img src={card.art} alt="" loading="lazy" />
      </button>}
      <div className="life-card-what">
        <span className="subtle">{card.veiled ? 'Life Card' : `Life Card · ${TONES[card.tone]}`}</span>
        <strong>{card.title}</strong>
      </div>
    </div>
  )
}
