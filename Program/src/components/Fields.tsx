import { useId, type ReactNode } from 'react'
import { InfoTip } from './InfoTip'
import { bounded } from './numberBounds'

/** Help for a control: `hint` shows under it, `tip` sits behind a "?" next to its label. Both are read out with it. */
interface Help { hint?: ReactNode; tip?: string }
interface FieldProps extends Help { label: string; children: (id: string, describedBy?: string) => ReactNode }

function joinIds(...ids: (string | false | undefined)[]) {
  return ids.filter(Boolean).join(' ') || undefined
}

/** A labelled control with an optional hint and tip read out with it. */
export function Field({ label, hint, tip, children }: FieldProps) {
  const id = useId()
  const hintId = hint ? `${id}-hint` : undefined
  const tipId = tip ? `${id}-tip` : undefined
  return (
    <div className="field">
      <span className="label-row"><label htmlFor={id}>{label}</label>{tip && tipId && <InfoTip id={tipId} label={label} text={tip} />}</span>
      {children(id, joinIds(hintId, tipId))}
      {hint && <small id={hintId}>{hint}</small>}
    </div>
  )
}

interface TextAreaProps extends Help { label: string; value: string; onChange: (value: string) => void; onBlur?: () => void; rows?: number; maxLength?: number; placeholder?: string; grows?: boolean }

/** `grows` makes it two lines tall, growing with its text (or placeholder) to about five. */
export function TextArea({ label, hint, tip, value, onChange, onBlur, rows = 3, maxLength, placeholder, grows }: TextAreaProps) {
  return <Field label={label} hint={hint} tip={tip}>{(id, describedBy) => <textarea id={id} rows={grows ? 2 : rows} className={grows ? 'grows' : undefined} value={value} maxLength={maxLength} placeholder={placeholder} aria-describedby={describedBy} onChange={(event) => onChange(event.target.value)} onBlur={onBlur} />}</Field>
}

interface TextInputProps extends Help { label: string; value: string; onChange: (value: string) => void; required?: boolean; maxLength?: number; list?: string; type?: string; placeholder?: string; min?: number; max?: number; step?: number }

/** With `min` or `max`, a number box keeps what is typed inside that range. */
export function TextInput({ label, hint, tip, value, onChange, required, maxLength, list, type = 'text', placeholder, min, max, step }: TextInputProps) {
  const leave = () => { const fixed = bounded(value, min, max, true); if (fixed !== value) onChange(fixed) }
  return <Field label={label} hint={hint} tip={tip}>{(id, describedBy) => <input id={id} type={type} value={value} required={required} maxLength={maxLength} list={list} placeholder={placeholder} min={min} max={max} step={step} aria-describedby={describedBy} onChange={(event) => onChange(bounded(event.target.value, min, max))} onBlur={leave} />}</Field>
}

interface ToggleProps extends Help { label: string; checked: boolean; onChange: (checked: boolean) => void; disabled?: boolean }

export function Toggle({ label, hint, tip, checked, onChange, disabled }: ToggleProps) {
  const id = useId()
  const hintId = hint ? `${id}-hint` : undefined
  const tipId = tip ? `${id}-tip` : undefined
  return (
    <div className="toggle">
      <input id={id} type="checkbox" checked={checked} disabled={disabled} aria-describedby={joinIds(hintId, tipId)} onChange={(event) => onChange(event.target.checked)} />
      <div className="toggle-text">
        <span className="label-row"><label htmlFor={id}>{label}</label>{tip && tipId && <InfoTip id={tipId} label={label} text={tip} />}</span>
        {hint && <small id={hintId}>{hint}</small>}
      </div>
    </div>
  )
}
