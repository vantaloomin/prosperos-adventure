import { STEPS, stepAt, type RoundLive, type RoundState } from './round'
import { STEP_NAMES, stepLine } from './roundText'

/** Declare · React · Talk · Roll · Write above who's here, the step under way lit and named under it ("Declaring · 2 of
 *  3"). The summary goes to a polite live region ("3 of 5 characters have decided"); the steps are not announced one
 *  by one. */
export function RoundTimeline({ state, live, summary }: { state: RoundState | null; live: RoundLive; summary: string }) {
  const at = stepAt(state)
  const line = stepLine(state, live)
  return (
    <div className="round-timeline">
      <ol aria-label="This turn">
        {STEPS.map((step, index) => <li key={step.key} className={index < at ? 'done' : index === at ? 'now' : undefined}
          aria-current={index === at ? 'step' : undefined}>{STEP_NAMES[step.key]}</li>)}
      </ol>
      {line && <p className="round-step" aria-hidden="true">{line}</p>}
      <p className="visually-hidden" role="status" aria-live="polite">{summary}</p>
    </div>
  )
}
