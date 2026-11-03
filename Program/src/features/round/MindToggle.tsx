import type { Mind } from './round'
import { MIND_NAMES } from './roundText'

/** Thinks (an agent) or Rules (a Program mind) for one character, as radio buttons. A change made during a turn counts
 *  from the next one. */
export function MindToggle({ id, name, mind, onChange }: { id: string; name: string; mind: Mind; onChange: (mind: 'agent' | 'program') => void }) {
  const thinks = mind === 'agent'
  return (
    <div className="segmented mind-toggle" role="radiogroup" aria-label={`How ${name} decides`}>
      <label><input type="radio" className="visually-hidden" name={`mind-${id}`} checked={thinks} onChange={() => onChange('agent')} /><span>{MIND_NAMES.agent}</span></label>
      <label><input type="radio" className="visually-hidden" name={`mind-${id}`} checked={!thinks} onChange={() => onChange('program')} /><span>{MIND_NAMES.program}</span></label>
    </div>
  )
}
