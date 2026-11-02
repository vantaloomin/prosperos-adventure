import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Globe, RotateCcw } from 'lucide-react'
import { api } from '../../api'
import type { MixTown, MixValues, TownsfolkMix as MixData } from '../../types'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { ErrorNotice } from '../../components/ErrorNotice'
import { Loading, Notice } from '../../components/Feedback'
import { Field } from '../../components/Fields'
import { enter } from '../worlds/useWorlds'
import {
  bandLine, bandRates, BOLDER_LABELS, type BuildKey, changesLine, DRIVE_LABELS, genderShares, LEVEL_NAMES, pct,
  rebalanceBuilds, sameMix, sharesLine, valueText,
} from './mixText'

const KEY = ['townsfolk-mix']
const DRIVE_NAMES = { low: 'low', average: 'average', high: 'high' }
const BUILDS = new Set(['slender', 'middle', 'heavier'])
type Change = (key: keyof MixValues, value: number) => void

/** Settings > Developer: the shares the townsfolk are drawn from, what this world's town is made of, and a new world made
 * with changed shares (dungeon/townsfolk_mix.py). Nothing changes here until a new world is made. */
export function TownsfolkMix() {
  const query = useQuery({ queryKey: KEY, queryFn: () => api<MixData>('/townsfolk-mix') })
  return (
    <section className="settings-section form-stack townsfolk-mix" aria-labelledby="townsfolk-mix-heading">
      <div>
        <h2 id="townsfolk-mix-heading">Townsfolk mix</h2>
        <p className="subtle">The shares the townsfolk are drawn from: how they look and who they're drawn to. Change them to make a new world with them. This world and everyone in it stay as they are.</p>
      </div>
      {query.isPending && <Loading label="Counting the townsfolk" />}
      {query.isError && <ErrorNotice error={query.error} />}
      {query.data && <MixForm data={query.data} />}
    </section>
  )
}

function MixForm({ data }: { data: MixData }) {
  const [draft, setDraft] = useState<MixValues>(data.mix)
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [problem, setProblem] = useState('')
  const change: Change = (key, value) => setDraft((before) => BUILDS.has(key)
    ? rebalanceBuilds(before, key as BuildKey, value) : { ...before, [key]: value })
  const make = async () => {
    setBusy(true)
    setProblem('')
    try {
      await api('/townsfolk-mix/new-world', { mix: draft })
      enter()
    } catch (failure) {
      setProblem(failure instanceof Error ? failure.message : 'That did not work. Try again.')
      setBusy(false)
      setConfirming(false)
    }
  }
  const city = data.town?.city ?? 'this city'
  return (
    <>
      {data.town && <TownNow town={data.town} adultSide={data.adult_side} />}
      {!sameMix(data.mix, data.defaults) && <Notice>This world was made with a changed mix. The sliders start from it.</Notice>}
      <LooksSliders data={data} draft={draft} change={change} />
      <DrawnToSliders data={data} draft={draft} change={change} />
      {data.adult_side && <AdultSliders data={data} draft={draft} change={change} />}
      <p className="subtle">Ages aren't part of the mix and stay as they are.</p>
      {problem && <Notice tone="error">{problem}</Notice>}
      <div className="form-actions wrap">
        <button type="button" className="button primary" disabled={busy} onClick={() => setConfirming(true)}><Globe aria-hidden="true" />Make a new world with this mix</button>
        <button type="button" className="text-button" disabled={busy || sameMix(draft, data.defaults)} onClick={() => setDraft(data.defaults)}><RotateCcw aria-hidden="true" />Back to the built-in mix</button>
      </div>
      {confirming && <Confirm city={city} changes={changesLine(draft, data.defaults)} busy={busy} make={make} close={() => setConfirming(false)} />}
    </>
  )
}

function Confirm({ city, changes, busy, make, close }: { city: string; changes: string; busy: boolean; make: () => Promise<void>; close: () => void }) {
  return <ConfirmDialog title="Make a new world with this mix?" onClose={() => { if (!busy) close() }} actions={<>
    <button type="button" className="button primary" disabled={busy} onClick={() => void make()}>{busy ? 'Making the world…' : 'Make it and go there'}</button>
    <button type="button" className="button" disabled={busy} onClick={close}>Cancel</button>
  </>}>
    <p>{changes ? <>Changes from the built-in mix: {changes}.</> : <>This is the built-in mix.</>}</p>
    <p>A new world in {city} for the persona you are now, with new townsfolk drawn from this mix. You'll go there now.</p>
    <p>This world and your story stay as they are. Come back any time from Worlds.</p>
  </ConfirmDialog>
}

/** What the town is made of now, counted from its people. */
function TownNow({ town, adultSide }: { town: MixTown; adultSide: boolean }) {
  const height = (cm: number | null) => cm ? heightLabel(cm) : 'none'
  return (
    <div className="form-stack">
      <h3>In {town.city} now</h3>
      <dl className="mix-now">
        <dt>People</dt><dd>{town.people.toLocaleString()} adult townsfolk</dd>
        <dt>Gender</dt><dd>{pct(town.genders.woman)} women, {pct(town.genders.man)} men, {pct(town.genders.nonbinary)} nonbinary</dd>
        <dt>Height</dt><dd>Women {height(town.heights.woman)}, men {height(town.heights.man)}</dd>
        <dt>Builds</dt><dd>Slender {pct(town.builds.slender)} · In between {pct(town.builds.middle)} · Heavier {pct(town.builds.heavier)}</dd>
        <dt>Facial hair</dt><dd>{pct(town.beard)} of men</dd>
        <dt>Drawn to</dt><dd>{pct(town.gay)} gay or lesbian, {pct(town.bisexual)} bisexual, of women and men</dd>
        {adultSide && <><dt>Adult side</dt><dd>{sharesLine(town.levels, LEVEL_NAMES)}; drive {sharesLine(town.drives, DRIVE_NAMES)}</dd></>}
      </dl>
      <p className="subtle">Counted from the people drawn here, so they land near the shares below rather than exactly on them. Sporty people are mostly athletic, which adds to the in-between builds.</p>
    </div>
  )
}

interface SlidersProps { data: MixData; draft: MixValues; change: Change }

function LooksSliders({ data, draft, change }: SlidersProps) {
  const genders = genderShares(draft)
  const slider = (key: keyof MixValues, label: string, shown: (value: number) => string, hint?: string) =>
    <MixSlider data={data} name={key} value={draft[key]} label={label} shown={shown} hint={hint} change={change} />
  return (
    <div className="form-stack">
      <h3>Looks</h3>
      {slider('nonbinary', 'Nonbinary people', pct, 'A third as many in worlds set in the past.')}
      {slider('women', 'Women and men', (value) => `${pct(value)} women, ${pct(100 - value)} men`,
        `Of everyone else. Altogether ${pct(genders.woman)} women, ${pct(genders.man)} men and ${pct(genders.nonbinary)} nonbinary people.`)}
      {slider('height_woman', "Women's average height", heightLabel, 'Nonbinary people average halfway between. People in older eras are a little shorter.')}
      {slider('height_man', "Men's average height", heightLabel)}
      {slider('slender', 'Slender builds', pct, 'Slim, petite, lean or wiry.')}
      {slider('middle', 'In-between builds', pct, 'Average, athletic, broad-shouldered or curvy.')}
      {slider('heavier', 'Heavier builds', pct, 'Soft, stocky, full-figured or heavyset. The three builds always add up to 100%: moving one shares the rest between the other two.')}
      {slider('beard', 'Men with facial hair', pct)}
    </div>
  )
}

function DrawnToSliders({ data, draft, change }: SlidersProps) {
  const rates = bandRates(data, draft)
  const of = (value: number) => `about ${pct(value)} of women and men`
  return (
    <div className="form-stack">
      <h3>Who they're drawn to</h3>
      <MixSlider data={data} name="gay" value={draft.gay} change={change} label="Gay or lesbian" shown={of}
        hint={`By age: ${bandLine(rates.map((rate) => ({ ages: rate.ages, value: rate.gay })))}.`} />
      <MixSlider data={data} name="bisexual" value={draft.bisexual} change={change} label="Bisexual" shown={of}
        hint={`By age: ${bandLine(rates.map((rate) => ({ ages: rate.ages, value: rate.bisexual })))}. Younger people more often, as in real surveys.`} />
      <p className="subtle">Nonbinary townsfolk are drawn to more than one gender and aren't part of these shares.</p>
    </div>
  )
}

function AdultSliders({ data, draft, change }: SlidersProps) {
  return (
    <div className="form-stack">
      <h3>Adult side</h3>
      <MixSlider data={data} name="bolder" value={draft.bolder} change={change} label="How adventurous" steps={BOLDER_LABELS}
        hint={`${sharesLine(data.levels[String(draft.bolder)], LEVEL_NAMES)}.`} />
      <MixSlider data={data} name="drive" value={draft.drive} change={change} label="Drive" steps={DRIVE_LABELS}
        hint={`${sharesLine(data.drives[String(draft.drive)], DRIVE_NAMES)}.`} />
    </div>
  )
}

interface MixSliderProps {
  data: MixData; name: keyof MixValues; value: number; label: string; change: Change; hint?: string
  shown?: (value: number) => string; steps?: Record<string, string>
}

/** One share: the slider holds it inside its limits, the label carries the value in words, and a value that differs
 * from the built-in mix says what the built-in one is. Named steps get a tick at each stop. */
function MixSlider({ data, name, value, label, change, hint, shown, steps }: MixSliderProps) {
  const [min, max, step] = data.limits[name]
  const words = (number: number) => steps ? steps[String(number)] ?? String(number) : (shown ?? String)(number)
  const builtIn = data.defaults[name]
  const note = Number(value) !== Number(builtIn) ? `Built-in: ${words(builtIn)}.` : ''
  const ticks = steps ? Object.keys(steps).map(Number).sort((a, b) => a - b) : []
  return <Field label={`${label}: ${words(value)}`} hint={[note, note && steps && hint ? `Now: ${hint}` : hint].filter(Boolean).join(' ') || undefined}>{(id, describedBy) => (
    <div className="mix-slider">
      <input id={id} type="range" min={min} max={max} step={step} value={value} list={steps ? `${id}-ticks` : undefined}
        aria-valuetext={valueText(name, value, steps)} aria-describedby={describedBy} onChange={(event) => change(name, Number(event.target.value))} />
      {steps && <>
        <datalist id={`${id}-ticks`}>{ticks.map((tick) => <option key={tick} value={tick} />)}</datalist>
        <div className="range-ticks" aria-hidden="true">
          {ticks.map((tick) => <span key={tick} style={{ left: `${(tick - min) / (max - min) * 100}%` }}>|</span>)}
        </div>
      </>}
    </div>
  )}</Field>
}

/** 5'7" (170 cm): both units, since the app is used on both sides of the Atlantic. */
function heightLabel(cm: number): string {
  const inches = Math.round(cm / 2.54)
  return `${Math.floor(inches / 12)}'${inches % 12}" (${cm} cm)`
}
