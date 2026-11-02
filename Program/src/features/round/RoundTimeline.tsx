import { STEPS, stepAt, type RoundState } from './round'

/** Declare · React · Converse · Resolve · Write, with the step under way lit, above who's here. The summary goes to a
 *  polite live region ("3 of 5 characters have decided"); the steps themselves are not announced one by one. */
export function RoundTimeline({ state, summary }: { state: RoundState | null; summary: string }) {
  const at = stepAt(state)
  return (
    <div className="round-timeline">
      <ol aria-label="This turn">
        {STEPS.map((step, index) => <li key={step.name} className={index < at ? 'done' : index === at ? 'now' : undefined}
          aria-current={index === at ? 'step' : undefined}>{step.name}</li>)}
      </ol>
      <p className="visually-hidden" role="status" aria-live="polite">{summary}</p>
    </div>
  )
}
