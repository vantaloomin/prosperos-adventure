import type { KindChoices, KindShown } from '../../types'
import { Field } from '../../components/Fields'
import { useKindChoices } from './useKindChoices'
import { asKindOption, foundOption, type KindSource, humanTermsText, spanChoices, yearsText } from './kindText'


interface Props {
  id: string
  shown: KindShown
  /** The kind the app picks when the user hasn't: their words', their parents' or their name's. */
  found: { kind: string; label: string; source: KindSource }
  picked: string
  /** How long they live as picked: null as their kind, 0 doesn't age. */
  own: number | null
  age?: number | null
  choices?: KindChoices
  /** Said under How long they live in place of nothing (Keeps their age is on). */
  note?: string
  /** On the Persona page: "How long you live", "As About you says". */
  you?: boolean
  onChange: (change: { kind: string; lifespan: number | null }) => void
}

/** Kind and How long they live: both start on the app's pick and only change when the user picks something else.
 * Lifespans are a list, never free text. The age shown elsewhere stays real; a small line gives it in human terms. */
export function KindFields({ id, shown, found, picked, own, age, choices, note, you = false, onChange }: Props) {
  const offered = useKindChoices(choices)
  const kinds = offered?.kinds ?? []
  const listed = kinds.find((item) => item.id === (picked || found.kind))
  const kindYears = listed ? listed.lifespan : shown.kind_years
  const hint = humanTermsText(shown, age)
  return (
    <div className="form-grid kind-fields">
      <Field label="Kind">{(fieldId, describedBy) => (
        <select id={fieldId} aria-describedby={describedBy} name={`${id}-kind`} value={picked} onChange={(event) => onChange({ kind: event.target.value, lifespan: own })}>
          <option value="">{foundOption(found.label, found.source, you)}</option>
          {kinds.filter((item) => !item.folk).map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
          {folks(kinds).map((folk) => (
            <optgroup key={folk} label={folk}>
              {kinds.filter((item) => item.folk === folk).map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
            </optgroup>
          ))}
        </select>
      )}</Field>
      <Field label={you ? 'How long you live' : 'How long they live'} hint={note}>{(fieldId, describedBy) => (
        <select id={fieldId} aria-describedby={describedBy} name={`${id}-lifespan`} value={own === null ? '' : String(own)}
          onChange={(event) => onChange({ kind: picked, lifespan: event.target.value === '' ? null : Number(event.target.value) })}>
          <option value="">{asKindOption(kindYears, you)}</option>
          {spanChoices(offered, own).map((years) => <option key={years} value={years}>About {yearsText(years)}</option>)}
          <option value="0">Doesn't age</option>
        </select>
      )}</Field>
      {hint && <small className="subtle kind-human-terms">{hint}</small>}
    </div>
  )
}

/** The peoples' groups in the order their first kind comes (Fantasy humanoids, Beastkin, Other peoples). */
function folks(kinds: { folk?: string | null }[]): string[] {
  return [...new Set(kinds.map((item) => item.folk).filter((folk): folk is string => Boolean(folk)))]
}
