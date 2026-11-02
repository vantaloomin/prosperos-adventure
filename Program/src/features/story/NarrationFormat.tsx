import type { TableRules } from '../../types'
import { Field } from '../../components/Fields'
import { LENGTHS, POVS, TENSES } from './storyText'

type Format = Pick<TableRules, 'pov' | 'tense' | 'length'>

/** How the narrator writes the story (dungeon/narration/prompt.py Format), kept at the Table (dungeon/table.py): point
 *  of view, tense and length. Changeable at any time; the next line follows it. */
export function NarrationFormat({ rules, onChange }: { rules: Format; onChange: (change: Format) => void }) {
  return (<>
    <Field label="Point of view" hint="Whose eyes the story is told through. The next line follows it.">
      {(id, describedBy) => <select id={id} value={rules.pov ?? 'third'} aria-describedby={describedBy}
        onChange={(event) => onChange({ pov: event.target.value as Format['pov'] })}>
        {POVS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select>}
    </Field>
    <Field label="Tense">
      {(id) => <select id={id} value={rules.tense ?? 'past'} onChange={(event) => onChange({ tense: event.target.value as Format['tense'] })}>
        {TENSES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select>}
    </Field>
    <Field label="Length" hint="How much the narrator writes each turn. Longer turns take longer to write.">
      {(id, describedBy) => <select id={id} value={rules.length ?? 'short'} aria-describedby={describedBy}
        onChange={(event) => onChange({ length: event.target.value as Format['length'] })}>
        {LENGTHS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select>}
    </Field>
  </>)
}
