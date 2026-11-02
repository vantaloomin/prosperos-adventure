import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { Minus, Plus } from 'lucide-react'
import { Field } from './Fields'
import { bounded, presetOptions } from './numberBounds'

interface Common { label: string; value: number; onChange: (value: number) => void; hint?: ReactNode; format: (value: number) => string }
interface Ranged extends Common { min: number; max: number }

/** A small count: [ - ] 3 events [ + ]. The buttons stop at the ends, so nothing out of range can be chosen. */
export function Stepper({ label, value, min, max, onChange, hint, format }: Ranged) {
  const id = useId()
  return <div className="field">
    <span className="label-row"><span className="field-label" id={`${id}-label`}>{label}</span></span>
    <div className="number-stepper" role="group" aria-labelledby={`${id}-label`} aria-describedby={hint ? `${id}-hint` : undefined}>
      {/* Marked rather than disabled at the ends, so keyboard focus stays on the button. */}
      <button type="button" className="stepper-button" aria-label="Fewer" aria-disabled={value <= min} onClick={() => { if (value > min) onChange(value - 1) }}><Minus aria-hidden="true" /></button>
      <output aria-live="polite">{format(value)}</output>
      <button type="button" className="stepper-button" aria-label="More" aria-disabled={value >= max} onClick={() => { if (value < max) onChange(value + 1) }}><Plus aria-hidden="true" /></button>
    </div>
    {hint && <small id={`${id}-hint`}>{hint}</small>}
  </div>
}

/**
 * A bounded count that can also be left unset: [ - ] Default [ + ]. More from "Default" starts at the least;
 * fewer from the least goes back to "Default".
 */
export function OptionalStepper({ label, value, min, max, onChange, hint, format }: Omit<Ranged, 'value' | 'onChange'> & { value: number | undefined; onChange: (value: number | undefined) => void }) {
  const id = useId()
  const fewer = () => { if (value !== undefined) onChange(value > min ? value - 1 : undefined) }
  const more = () => { if (value === undefined) onChange(min); else if (value < max) onChange(value + 1) }
  return <div className="field">
    <span className="label-row"><span className="field-label" id={`${id}-label`}>{label}</span></span>
    <div className="number-stepper" role="group" aria-labelledby={`${id}-label`} aria-describedby={hint ? `${id}-hint` : undefined}>
      <button type="button" className="stepper-button" aria-label="Fewer" aria-disabled={value === undefined} onClick={fewer}><Minus aria-hidden="true" /></button>
      <output aria-live="polite">{value === undefined ? 'Default' : format(value)}</output>
      <button type="button" className="stepper-button" aria-label="More" aria-disabled={value !== undefined && value >= max} onClick={more}><Plus aria-hidden="true" /></button>
    </div>
    {hint && <small id={`${id}-hint`}>{hint}</small>}
  </div>
}

/** A time span from friendly presets; a saved value that is not a preset stays listed, so nothing changes silently. */
export function PresetSelect({ label, value, presets, onChange, hint, format }: Common & { presets: number[] }) {
  return <Field label={label} hint={hint}>{(id, describedBy) => (
    <select id={id} aria-describedby={describedBy} value={value} onChange={(event) => onChange(Number(event.target.value))}>
      {presetOptions(presets, value, format).map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
    </select>
  )}</Field>
}

/** Waits until the value stops moving before saving it, so dragging a slider saves once. */
function useSettled(value: number, onChange: (value: number) => void, delay = 400) {
  const [moving, setMoving] = useState<number | null>(null)
  const timer = useRef<number | undefined>(undefined)
  useEffect(() => () => window.clearTimeout(timer.current), [])
  const move = (next: number) => {
    setMoving(next)
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => { setMoving(null); if (next !== value) onChange(next) }, delay)
  }
  return [moving ?? value, move] as const
}

/** A wider count: a slider with the live value in its label. Saves once the value settles. */
export function SliderField({ label, value, min, max, onChange, hint, format }: Ranged) {
  const [shown, move] = useSettled(value, onChange)
  return <Field label={`${label}: ${format(shown)}`} hint={hint}>{(id, describedBy) => (
    <input id={id} type="range" min={min} max={max} step={1} value={shown} aria-valuetext={format(shown)} aria-describedby={describedBy}
      onChange={(event) => move(Number(event.target.value))} />
  )}</Field>
}

/** Technical tuning: a slider showing the usual range beside a box for an exact value, kept in range on leaving it. */
export function SliderNumber({ label, value, min, max, step, onChange, hint }: Omit<Ranged, 'format'> & { step: number }) {
  const [text, setText] = useState<string | null>(null)
  const leave = () => {
    if (text !== null && text.trim() !== '' && Number.isFinite(Number(text))) onChange(Number(bounded(text, min, max, true)))
    setText(null)
  }
  return <Field label={label} hint={hint}>{(id, describedBy) => (
    <div className="slider-number">
      <input type="range" min={min} max={max} step={step} value={value} aria-label={label} onChange={(event) => onChange(Number(event.target.value))} />
      <input id={id} type="number" inputMode="decimal" min={min} max={max} step={step} value={text ?? String(value)} aria-describedby={describedBy}
        onChange={(event) => setText(bounded(event.target.value, min, max))} onBlur={leave} />
    </div>
  )}</Field>
}
