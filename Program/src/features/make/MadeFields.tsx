import type { PersonaGender } from '../../types'
import { TextArea, TextInput } from '../../components/Fields'
import { GENDERS } from '../worlds/worldsText'
import { QuickStart } from './QuickStart'
import { SheetExtras } from './SheetExtras'
import { MAKE_TEXT, type MadeForm } from './makeText'

interface Props {
  form: MadeForm
  onChange: (form: MadeForm) => void
  onAddModel?: () => void
  /** A party member the player makes, not the character they play: the model is told so. */
  party?: boolean
}

/** A made character's form (adventure/making.py): the quick start, who they are, how they look and talk, what they
 * want and fear, then personality, Looks and how they come across, folded. The cast page's own character and the
 * party members made there share it. */
export function MadeFields({ form, onChange, onAddModel, party }: Props) {
  const set = (change: Partial<MadeForm>) => onChange({ ...form, ...change })
  return <>
    <QuickStart form={form} onDraft={onChange} onAddModel={onAddModel} party={party} />
    <TextInput label="Name" value={form.name} onChange={(name) => set({ name })} required maxLength={80} />
    <label className="field">Gender
      <select value={form.gender} onChange={(event) => set({ gender: event.target.value as PersonaGender })}>
        {GENDERS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select>
    </label>
    <TextInput label="Age" type="number" value={form.age} onChange={(age) => set({ age })} min={18} max={120} />
    <TextArea label={party ? MAKE_TEXT.about : MAKE_TEXT.aboutYou} value={form.about} onChange={(about) => set({ about })} rows={4} maxLength={2000} />
    <TextArea label={MAKE_TEXT.look} value={form.look} onChange={(look) => set({ look })} grows maxLength={600} />
    <TextArea label={MAKE_TEXT.voice} value={form.voice} onChange={(voice) => set({ voice })} grows maxLength={600} />
    <TextInput label={MAKE_TEXT.wants} value={form.wants} onChange={(wants) => set({ wants })} maxLength={300} />
    <TextInput label={MAKE_TEXT.fears} value={form.fears} onChange={(fears) => set({ fears })} maxLength={300} />
    <SheetExtras form={form} set={set} party={party} />
  </>
}
