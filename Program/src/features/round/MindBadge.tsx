import { Brain, ListChecks } from 'lucide-react'
import type { Mind } from './round'

/** Whether a character thinks for themselves (an agent) or goes by the rules (a Program mind): icon and text, in the
 *  cast list only, never in the story. */
export function MindBadge({ mind }: { mind: Mind }) {
  if (mind === 'human') return null
  return mind === 'agent'
    ? <span className="mind-badge thinks"><Brain aria-hidden="true" />Thinks</span>
    : <span className="mind-badge"><ListChecks aria-hidden="true" />Rules</span>
}

/** Thinks or Rules for one character, as radio buttons. A change made during a turn counts from the next one. */
export function MindToggle({ id, name, mind, onChange }: { id: string; name: string; mind: Mind; onChange: (mind: 'agent' | 'program') => void }) {
  const thinks = mind === 'agent'
  return (
    <div className="segmented mind-toggle" role="radiogroup" aria-label={`How ${name} decides`}>
      <label><input type="radio" className="visually-hidden" name={`mind-${id}`} checked={thinks} onChange={() => onChange('agent')} /><span><Brain aria-hidden="true" />Thinks</span></label>
      <label><input type="radio" className="visually-hidden" name={`mind-${id}`} checked={!thinks} onChange={() => onChange('program')} /><span><ListChecks aria-hidden="true" />Rules</span></label>
    </div>
  )
}
