import { useState } from 'react'
import { api } from '../../api'
import type { KindChoices, Persona, PersonaGender, World, Worlds } from '../../types'
import { Field, TextArea, TextInput } from '../../components/Fields'
import { Notice } from '../../components/Feedback'
import { GENDERS, ageHint } from './worldsText'
import { KindFields } from '../kinds/KindFields'
import { lifeAge, longLived, pickedLifespan } from '../kinds/kindText'
import { CityPick, SOMEWHERE_NEW } from './CityPick'
import { PersonaHome } from './PersonaHome'
import { homeChanged, saveHome, useHomeDraft, type HomeDraft } from './personaHomeText'

const BIRTHDAY = /^(?:(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01]))?$/

type Draft = { name: string; gender: PersonaGender; age: string; about: string; birthday: string; kind: string; lifespan: number | null }

function draftOf(persona?: Persona): Draft {
  if (!persona) return { name: '', gender: '', age: '', about: '', birthday: '', kind: '', lifespan: null }
  return { name: persona.name, gender: persona.gender, age: persona.age ? String(persona.age) : '', about: persona.about, birthday: persona.birthday,
    kind: persona.kind ?? '', lifespan: persona.lifespan ?? null }
}

/** A new persona needs the name the user gives it; everything else may stay blank. Past 120 only for a long-lived
 * kind. */
function validDraft(draft: Draft, age: number | null, isNew: boolean, long: boolean): boolean {
  return (age === null || ageHint(age, long) === undefined) && BIRTHDAY.test(draft.birthday) && (!isNew || !!draft.name.trim())
}

const TEXT = {
  existing: { id: 'persona-heading', heading: 'Who you are here', button: 'Save', busy: 'Saving…', intro: 'The narrator and the people in this persona\'s worlds know you by this.' },
  new: { id: 'new-persona-heading', heading: 'A new persona', button: 'Make this persona', busy: 'Making their world…', intro: 'Who will you be? They get a world of their own with new people in it.' },
}

/** A new persona, with their world in `city`, or the changes to one; a new one's form closes once it is made. */
async function savePersona(persona: Persona | undefined, body: Omit<Draft, 'age'> & { age: number | null }, city: string): Promise<Worlds | undefined> {
  if (!persona) { await api('/worlds/personas', { ...body, city_id: city }); return undefined }
  return api<Worlds>(`/worlds/personas/${persona.id}`, body, 'PATCH')
}

/** The persona, then where they live in the world they are in when the user changed it. */
async function saveAll(persona: Persona | undefined, body: Parameters<typeof savePersona>[1], city: string, moving?: { world: World; home: HomeDraft } | null): Promise<Worlds | undefined> {
  const saved = await savePersona(persona, body, city)
  return moving && homeChanged(moving.world, moving.home) ? saveHome(moving.world, moving.home) : saved
}

/** `cityId` is the city the user is in now, listed in a new persona's city picker even before the cities load.
 * `world` is the world the persona is in now, where the form also says where they live. */
interface PersonaFormProps { persona?: Persona; world?: World; cityId: string; onSaved: (data?: Worlds) => void; onCancel?: () => void
  /** What the Kind pickers offer, for a new persona (the one in use carries its own). */
  kinds?: KindChoices }

/** Who the user is: the one in use, or (without `persona`) a new one. Only the user says this; the narrator knows
 * only what is written here, and nothing left blank is made up. */
export function PersonaForm({ persona, world, cityId, onSaved, onCancel, kinds }: PersonaFormProps) {
  const [draft, setDraft] = useState(() => draftOf(persona))
  const home = useHomeDraft(world)
  const [city, setCity] = useState(SOMEWHERE_NEW)
  const [saving, setSaving] = useState(false)
  const text = persona ? TEXT.existing : TEXT.new
  const headingId = text.id
  const [note, setNote] = useState<{ tone: 'info' | 'error'; text: string } | null>(null)
  const set = (change: Partial<typeof draft>) => { setDraft((old) => ({ ...old, ...change })); setNote(null) }
  const age = draft.age ? Number(draft.age) : null
  const { choices, span, found } = kindState(persona, kinds, draft)
  const long = longLived(span)
  const valid = validDraft(draft, age, !persona, long)
  const save = async () => {
    setSaving(true)
    try {
      const saved = await saveAll(persona, { ...draft, age }, city, home.moving)
      home.settle(saved)
      onSaved(saved)
      setNote({ tone: 'info', text: 'Saved. The narrator knows you this way from the next turn.' })
    } catch (failure) { setNote({ tone: 'error', text: failure instanceof Error ? failure.message : 'That was not saved.' }) } finally { setSaving(false) }
  }
  return (
    <form className="settings-section form-stack persona-form" aria-labelledby={headingId} onSubmit={(event) => { event.preventDefault(); if (valid) void save() }}>
      <div>
        <h2 id={headingId}>{text.heading}</h2>
        <p className="subtle">{text.intro} Leave anything but the name blank to keep it to yourself.</p>
      </div>
      <TextInput label="Name" value={draft.name} maxLength={80} required={!persona} onChange={(name) => set({ name })} />
      <Field label="Gender">{(id, describedBy) => (
        <select id={id} aria-describedby={describedBy} value={draft.gender} onChange={(event) => set({ gender: event.target.value as PersonaGender })}>
          {GENDERS.map(([value, label]) => <option key={value || 'none'} value={value}>{label}</option>)}
        </select>
      )}</Field>
      {choices && <PersonaKind found={found} choices={choices} draft={draft} age={age} span={span} set={set} />}
      <AgeField value={draft.age} age={age} long={long} onChange={(value) => set({ age: value })} />
      <TextInput label="Birthday" value={draft.birthday} placeholder="MM-DD" maxLength={5} onChange={(birthday) => set({ birthday })}
        hint="Month and day, like 04-23. The story keeps track of your age from it." />
      <TextArea label="About you" value={draft.about} rows={3} maxLength={2000} onChange={(about) => set({ about })}
        placeholder="Works nights as a paramedic, loves old films." />
      <PersonaHome moving={home.moving} disabled={saving} onChange={(next) => { home.setHome(next); setNote(null) }} />
      {!persona && <CityPick value={city} currentId={cityId} disabled={saving} onChange={setCity} />}
      <div className="form-actions">
        <button type="submit" className="button primary" disabled={!valid || saving}>{saving ? text.busy : text.button}</button>
        {onCancel && <button type="button" className="text-button" onClick={onCancel}>Cancel</button>}
      </div>
      {note && <Notice tone={note.tone}>{note.text}</Notice>}
    </form>
  )
}

/** The choices the Kind pickers offer and how long the persona lives as the draft stands (null: they don't age). */
function kindState(persona: Persona | undefined, kinds: KindChoices | undefined, draft: Draft) {
  const choices = persona?.kind_shown ?? kinds
  const found = foundKind(persona?.kind_shown)
  return { choices, found, span: choices ? pickedLifespan(choices, draft.kind, draft.lifespan, found.years) : 80 }
}

/** The kind the app read from About you (as last saved), human for a new persona. */
function foundKind(shown: Persona['kind_shown']) {
  if (!shown) return { kind: 'human', label: 'Human', years: 80 }
  const listed = shown.kinds.find((item) => item.id === shown.found)
  return { kind: shown.found, label: shown.found_label, years: listed ? listed.lifespan : 80 }
}

interface PersonaKindProps { found: { kind: string; label: string; years: number | null }; choices: KindChoices; draft: Draft; age: number | null; span: number | null; set: (change: Partial<Draft>) => void }

/** Kind and How long you live (dungeon/world/lifespans.py), as on the Character page: read from About you until
 * the user picks. */
function PersonaKind({ found, choices, draft, age, span, set }: PersonaKindProps) {
  const life = age === null || span === 80 ? null : lifeAge(age, span)
  return <KindFields id="persona" you choices={choices} age={age}
    shown={{ kind: draft.kind || found.kind, label: '', own: draft.lifespan, years: span, kind_years: span, life_age: life }}
    found={{ kind: found.kind, label: found.label, source: found.kind !== 'human' ? 'words' : 'app' }}
    picked={draft.kind} own={draft.lifespan} onChange={({ kind, lifespan }) => set({ kind, lifespan })} />
}

/** Age as a number: blank keeps it unsaid, 18 and up. Up to 5,000 can be typed so the hint can say past 120 needs a
 * long-lived kind. */
function AgeField({ value, age, long, onChange }: { value: string; age: number | null; long: boolean; onChange: (value: string) => void }) {
  return <TextInput label="Age" type="number" value={value} min={18} max={5000} step={1} placeholder="Not said"
    hint={ageHint(age, long)} onChange={onChange} />
}
