import { useEffect, useRef, useState } from 'react'
import { CircleHelp } from 'lucide-react'

interface Props { id: string; label: string; text: string; above?: boolean }

/**
 * A small "?" next to a label with a sentence or two of extra detail. It opens on hover, on keyboard
 * focus and on click or tap, and Escape closes it. The text stays in the page, so the field it explains
 * can list `id` in its aria-describedby and screen readers hear it without opening anything.
 */
export function InfoTip({ id, label, text, above }: Props) {
  const [pinned, setPinned] = useState(false)
  const [hovered, setHovered] = useState(false)
  const [focused, setFocused] = useState(false)
  const box = useRef<HTMLSpanElement>(null)
  const open = pinned || hovered || focused
  useEffect(() => {
    if (!open) return
    const close = (event: KeyboardEvent) => { if (event.key === 'Escape') { setPinned(false); setHovered(false); setFocused(false) } }
    const outside = (event: PointerEvent) => { if (!box.current?.contains(event.target as Node)) setPinned(false) }
    document.addEventListener('keydown', close)
    document.addEventListener('pointerdown', outside)
    return () => { document.removeEventListener('keydown', close); document.removeEventListener('pointerdown', outside) }
  }, [open])
  return (
    <span ref={box} className={above ? 'info-tip above' : 'info-tip'} onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)}>
      <button type="button" className="info-tip-button" aria-label={`More about ${label}`} aria-describedby={id} aria-expanded={open}
        onClick={() => setPinned((value) => !value)} onFocus={() => setFocused(true)} onBlur={() => { setFocused(false); setPinned(false) }}>
        <CircleHelp aria-hidden="true" />
      </button>
      <span id={id} role="tooltip" className="info-tip-text" hidden={!open}>{text}</span>
    </span>
  )
}

