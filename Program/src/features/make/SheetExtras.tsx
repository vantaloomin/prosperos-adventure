import { useEffect, useId, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Dices, X } from 'lucide-react'
import { api } from '../../api'
import { Field } from '../../components/Fields'
import {
  LOOKS_LABELS, MAKE_TEXT, NUMBER_LOOKS, WORD_LOOKS, drawnLabel, heightLabel, levelLabel, moved, numberChoices, released,
  sameSliders, sheetBody, sourceLabel, weightLabel,
  type LooksView, type MadeForm, type PerceptionView, type PersonalityKey, type PersonalitySlider,
  type PersonalityTrait, type PersonalityView,
} from './makeText'

interface Props { form: MadeForm; set: (change: Partial<MadeForm>) => void; party?: boolean }

/** The form once typing pauses, so the rolls follow it without a request per keystroke. */
function useSettled<T>(value: T, delay = 600): T {
  const [settled, setSettled] = useState(value)
  const key = JSON.stringify(value)
  useEffect(() => {
    const timer = window.setTimeout(() => setSettled(JSON.parse(key) as T), delay)
    return () => window.clearTimeout(timer)
  }, [key, delay])
  return settled
}

/** Under About you: personality, Looks and how they come across, each folded, each rolled from the form's seed and
 * kept where the person sets it (adventure/making.py). Nothing here needs a model. */
export function SheetExtras({ form, set, party }: Props) {
  return <>
    <Personality form={form} set={set} />
    <LooksFields form={form} set={set} />
    <Perception form={form} set={set} words={party ? MAKE_TEXT.them : MAKE_TEXT.you} />
  </>
}

function Personality({ form, set }: Props) {
  // How others see you and how you see yourself never change the sliders, so typing in them asks for nothing.
  const body = useSettled({ ...sheetBody(form), seen_as: '', sees_self: '' })
  const found = useQuery({
    queryKey: ['make-personality', body],
    queryFn: () => api<PersonalityView>('/story/make/personality', body),
    staleTime: Infinity,
    placeholderData: (previous) => previous,
  })
  const [error, setError] = useState('')
  useEffect(() => {
    if (found.data && !sameSliders(found.data.sliders, form.personality_sliders)) set({ personality_sliders: found.data.sliders })
    // Only a new answer from the app changes the form; the form's own changes ask again through `body`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [found.data])
  if (!found.data) return null
  const sliders = form.personality_sliders ?? found.data.sliders
  const roll = async () => {
    setError('')
    try {
      const result = await api<PersonalityView>('/story/make/personality', { ...sheetBody(form), personality_sliders: sliders, roll: Math.floor(Math.random() * 999_999) + 1 })
      set({ personality_sliders: result.sliders })
    } catch (failure) { setError(failure instanceof Error ? failure.message : MAKE_TEXT.failed) }
  }
  return (
    <details className="make-more">
      <summary>{MAKE_TEXT.personality}<span className="make-value">{found.data.chips.join(', ')}</span></summary>
      <div className="make-sliders">
        {found.data.traits.map((trait) => <SliderRow key={trait.key} trait={trait} slider={sliders[trait.key] ?? { level: 1, source: 'rolled' }}
          onMove={(level) => set({ personality_sliders: moved(sliders, trait.key, level) })}
          onRelease={() => set({ personality_sliders: released(sliders, trait.key as PersonalityKey) })} />)}
      </div>
      <button type="button" className="button quiet make-roll" onClick={() => void roll()}><Dices aria-hidden="true" />{MAKE_TEXT.roll}</button>
      {error && <p className="field-help-error" role="alert">{error}</p>}
    </details>
  )
}

interface RowProps { trait: PersonalityTrait; slider: PersonalitySlider; onMove: (level: number) => void; onRelease: () => void }

/** One slider, three stops: its name, where it sits in words, and who set it (SE-5: a label and a value). */
function SliderRow({ trait, slider, onMove, onRelease }: RowProps) {
  const id = useId()
  return (
    <div className="make-slider">
      <div className="make-slider-top">
        <label htmlFor={id}>{trait.name}</label>
        <span className="make-slider-value">{levelLabel(trait, slider.level)}</span>
        <span className="make-tag">{sourceLabel(slider.source)}
          {slider.source === 'you' && <button type="button" className="make-tag-reset" aria-label={MAKE_TEXT.handBack(trait.name)} title={MAKE_TEXT.handBack(trait.name)} onClick={onRelease}><X aria-hidden="true" /></button>}
        </span>
      </div>
      <input id={id} type="range" min={0} max={2} step={1} value={slider.level} aria-valuetext={levelLabel(trait, slider.level)}
        onChange={(event) => onMove(Number(event.target.value))} />
    </div>
  )
}

function LooksFields({ form, set }: Props) {
  const body = useSettled({ ...sheetBody(form), seen_as: '', sees_self: '' })
  const found = useQuery({
    queryKey: ['make-looks', body],
    queryFn: () => api<LooksView>('/story/make/looks', body),
    staleTime: Infinity,
    placeholderData: (previous) => previous,
  })
  const drawn = found.data?.automatic
  const change = (field: keyof MadeForm['looks'], value: string | number | null) => set({ looks: { ...form.looks, [field]: value } })
  return (
    <details className="make-more">
      <summary>{MAKE_TEXT.looks}</summary>
      <div className="make-looks">
        {NUMBER_LOOKS.map((field) => {
          const format = field === 'height_cm' ? heightLabel : weightLabel
          const value = form.looks[field] ?? null
          const choices = numberChoices(field)
          const listed = value !== null && !choices.includes(value) ? [...choices, value].sort((a, b) => a - b) : choices
          return <Field key={field} label={LOOKS_LABELS[field]}>{(id) => (
            <select id={id} value={value ?? ''} onChange={(event) => change(field, event.target.value ? Number(event.target.value) : null)}>
              <option value="">{drawn ? drawnLabel(drawn[field], format) : ''}</option>
              {listed.map((choice) => <option key={choice} value={choice}>{format(choice)}</option>)}
            </select>
          )}</Field>
        })}
        {WORD_LOOKS.map((field) => <Field key={field} label={LOOKS_LABELS[field]}>{(id) => (
          <input id={id} type="text" autoComplete="off" maxLength={field === 'hair' || field === 'feature' ? 200 : 120} value={form.looks[field] ?? ''}
            placeholder={drawn ? drawnLabel(drawn[field]) : ''} onChange={(event) => change(field, event.target.value)} />
        )}</Field>)}
      </div>
    </details>
  )
}

/** How they come across, in the words of whoever is being made: you, or a party member. */
function Perception({ form, set, words }: Props & { words: typeof MAKE_TEXT.you }) {
  const body = useSettled({ ...sheetBody(form), seen_as: '', sees_self: '' })
  const found = useQuery({
    queryKey: ['make-perception', body],
    queryFn: () => api<PerceptionView>('/story/make/perception', body),
    staleTime: Infinity,
    placeholderData: (previous) => previous,
  })
  const automatic = found.data?.automatic
  return (
    <details className="make-more">
      <summary>{words.seen}</summary>
      <Pickable label={words.seenAs} pick={words.pickSeenAs} value={form.seen_as} rows={2} maxLength={400}
        placeholder={automatic?.seen_as ?? ''} options={found.data?.seen_as ?? []} onChange={(seen_as) => set({ seen_as })} />
      <Pickable label={words.seesSelf} pick={words.pickSeesSelf} value={form.sees_self} rows={4} maxLength={1200}
        placeholder={automatic?.sees_self ?? ''} options={found.data?.sees_self ?? []} onChange={(sees_self) => set({ sees_self })} />
    </details>
  )
}

interface PickableProps { label: string; pick: string; value: string; rows: number; maxLength: number; placeholder: string; options: string[]; onChange: (value: string) => void }

/** Free text, or one of the app's picks that fits; left empty, the first pick (shown as the placeholder) is used. */
function Pickable({ label, pick, value, rows, maxLength, placeholder, options, onChange }: PickableProps) {
  return (
    <Field label={label}>{(id) => (
      <div className="make-pickable">
        <textarea id={id} rows={rows} value={value} maxLength={maxLength} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} />
        {options.length > 1 && <select aria-label={pick} value="" onChange={(event) => { if (event.target.value) onChange(event.target.value) }}>
          <option value="">{pick}</option>
          {options.map((option) => <option key={option} value={option}>{option.split('\n')[0]}{option.includes('\n') ? ' …' : ''}</option>)}
        </select>}
      </div>
    )}</Field>
  )
}

