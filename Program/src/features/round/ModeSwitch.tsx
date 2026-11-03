import { MODES, type Mode } from './round'
import { MODE_LABEL, MODE_NAMES } from './roundText'

/** Play, Author or Watch, in the scene line (PL-2). A change made during a turn counts from the next one. */
export function ModeSwitch({ shown, mode, onChange }: { shown: boolean; mode: Mode; onChange: (mode: Mode) => void }) {
  if (!shown) return null
  return (
    <div className="segmented mode-switch" role="radiogroup" aria-label={MODE_LABEL}>
      {MODES.map((key) => <label key={key}>
        <input type="radio" className="visually-hidden" name="round-mode" checked={mode === key} onChange={() => onChange(key)} />
        <span>{MODE_NAMES[key]}</span>
      </label>)}
    </div>
  )
}
