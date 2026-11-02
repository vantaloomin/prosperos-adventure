import { useState } from 'react'
import type { DefeatRule, InjuryPersistence, Ruleset, LegacyCandidate, LegacyRole, StoryArc, StoryHand, StoryIntensity, StoryPace, StoryStart as StartChoices, TablePreset, TableRules } from '../../types'
import { Field, Toggle } from '../../components/Fields'
import { NarrationFormat } from './NarrationFormat'
import { ARC_NAMES, dramaChoices, HAND_NAMES, intensityChoices, LEGACY_ROLES, PACE_NAMES } from './storyText'

type Legacy = { world_id: string; role: LegacyRole }
type Tone = Pick<TableRules, 'intensity' | 'drama' | 'injury_persistence' | 'defeat'>
type Taste = Pick<TableRules, 'show_odds' | 'roll_dice'>
type Format = Pick<TableRules, 'pov' | 'tense' | 'length'>

const INJURIES: [InjuryPersistence, string][] = [['permanent', 'Permanent: they stay'],
  ['temporary', 'Temporary: they fade with time'], ['none', 'None: wounds heal clean']]

interface Props {
  choices: StartChoices; intensity?: StoryIntensity; ruleset?: Ruleset; who: string; busy: boolean
  onStart: (body: Record<string, unknown>) => void; onBack: () => void
}

/** Session zero (docs/story.md "The Table"): before play, what kind of game this is. A preset sets the tone and the
 *  director's hand, the world's own pre-picked so Start is one click away; "Fine-tune" shows every rule it set, and the
 *  rest of what is chosen once for the campaign. */
export function SessionZero({ choices, intensity, ruleset, who, busy, onStart, onBack }: Props) {
  const { presets, preset, pick, rules, steer, setTone, setTaste, setFormat, setHand, campaign, setCampaign, body } = useSession(choices)
  return (
    <section className="session-zero" aria-labelledby="session-zero-heading">
      <h2 id="session-zero-heading">How this campaign plays</h2>
      <p className="subtle">Playing as {who}. Pick how the story treats you; you can change the tone later under Tone and rules.</p>
      <PresetCards presets={presets} value={preset.id} onChange={pick} />
      <details className="session-fine-tune">
        <summary>Fine-tune</summary>
        <ToneFields rules={rules} intensity={intensity} onChange={setTone} />
        {ruleset === 'srd52' && <DefeatField value={rules.defeat ?? 'as_written'} onChange={(defeat) => setTone({ defeat })} />}
        <NarrationFormat rules={rules} onChange={setFormat} />
        {choices.arc && <HandField value={steer} onChange={setHand} />}
        {ruleset === 'narrative' ? <p className="subtle">Narrative has no dice to show: each try is judged No, No but, Yes but or Yes, and the story tells it.</p>
          : <TasteFields rules={rules} onChange={setTaste} />}
        <CampaignFields choices={choices} value={campaign} onChange={setCampaign} />
      </details>
      <div className="form-actions">
        <button type="button" className="button primary" disabled={busy} onClick={() => onStart(body)}>{busy ? 'Starting…' : 'Start'}</button>
        <button type="button" className="button" disabled={busy} onClick={onBack}>Back</button>
      </div>
    </section>
  )
}

/** Session zero's choices: the preset picked, and what fine-tuning changed on top of it. */
function useSession(choices: StartChoices) {
  const presets = choices.presets ?? []
  const [presetId, setPresetId] = useState(presets[0]?.id ?? '')
  const [tone, setTone] = useState<Partial<Tone>>({})
  const [taste, setTaste] = useState<Partial<Taste>>({})
  const [format, setFormat] = useState<Format>({})
  const [hand, setHand] = useState<StoryHand | null>(null)
  const [campaign, setCampaign] = useState<Campaign>({ arc: null, pace: null, ironman: false, legacy: null })
  const preset: TablePreset | { id: string; rules?: undefined; hand?: undefined } = presets.find((item) => item.id === presetId) ?? presets[0] ?? { id: '' }
  const pick = (id: string) => { setPresetId(id); setTone({}); setHand(null) }
  const chosen = { ...preset.rules, ...tone, ...taste, ...format }
  const steer = hand ?? steerOf(preset.hand, choices)
  const { ironman, ...rest } = campaign
  return {
    presets, preset, pick, steer, campaign, setCampaign, setHand,
    rules: { ...choices.table, ...chosen } as TableRules,
    setTone: (change: Partial<Tone>) => setTone({ ...tone, ...change }),
    setTaste: (change: Partial<Taste>) => setTaste({ ...taste, ...change }),
    setFormat: (change: Format) => setFormat({ ...format, ...change }),
    body: { table: chosen, ...given({ ...rest, hand: choices.arc && steer }), ironman },
  }
}

/** The director's hand a preset sets, or the world's own. */
function steerOf(hand: StoryHand | null | undefined, choices: StartChoices): StoryHand {
  return hand ?? choices.arc?.hand ?? 'guiding'
}

function HandField({ value, onChange }: { value: StoryHand; onChange: (hand: StoryHand) => void }) {
  return (
    <Field label="How hard the story pushes" hint="How a game master's hand steers toward the larger story. It never decides what you do, or the dice.">
      {(id, describedBy) => <select id={id} value={value} aria-describedby={describedBy} onChange={(event) => onChange(event.target.value as StoryHand)}>
        {(Object.entries(HAND_NAMES) as [StoryHand, string][]).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
      </select>}
    </Field>
  )
}

/** What the player sees of the dice: starts as they left it last campaign. */
function TasteFields({ rules, onChange }: { rules: TableRules; onChange: (change: Partial<Taste>) => void }) {
  return (<>
    <Toggle label="Show the dice" checked={rules.show_odds} onChange={(checked) => onChange({ show_odds: checked })}
      hint="Each roll under your line. Off, you feel the dice only through the story. Starts as you left it last time." />
    {rules.show_odds && <Toggle label="Roll the dice on screen" checked={rules.roll_dice} onChange={(checked) => onChange({ roll_dice: checked })}
      hint="Dice roll across the story and land on the game's own roll before its result shows." />}
  </>)
}

/** Under 5E only: a defeat at 0 hit points by the death saves as written, or by what the foes were after. */
function DefeatField({ value, onChange }: { value: DefeatRule; onChange: (defeat: DefeatRule) => void }) {
  return <Toggle label="Foes decide a defeat" checked={value === 'by_aim'} onChange={(checked) => onChange(checked ? 'by_aim' : 'as_written')}
    hint="Off: at 0 hit points the death saves decide, as written. On: only foes out to kill bring the death saves; others take what they came for." />
}

function PresetCards({ presets, value, onChange }: { presets: TablePreset[]; value: string; onChange: (id: string) => void }) {
  return (
    <fieldset className="session-presets">
      <legend className="visually-hidden">Preset</legend>
      {presets.map((item) => (
        <label key={item.id} className={item.id === value ? 'session-preset picked' : 'session-preset'}>
          <input type="radio" name="session-preset" value={item.id} checked={item.id === value} onChange={() => onChange(item.id)} />
          <strong>{item.name}</strong>
          <span className="subtle">{item.about}</span>
        </label>
      ))}
    </fieldset>
  )
}

function ToneFields({ rules, intensity, onChange }: { rules: TableRules; intensity?: StoryIntensity; onChange: (change: Partial<Tone>) => void }) {
  return (<>
    <Field label="How far the story goes" hint="Violence, sex, horror, cruelty and drugs on the page.">
      {(id, describedBy) => <select id={id} value={rules.intensity} aria-describedby={describedBy} onChange={(event) => onChange({ intensity: event.target.value as Tone['intensity'] })}>
        {intensityChoices(intensity?.world ?? 'mature').map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select>}
    </Field>
    <Field label="How eventful" hint="How often the world throws something at you. It never changes the dice.">
      {(id, describedBy) => <select id={id} value={rules.drama} aria-describedby={describedBy} onChange={(event) => onChange({ drama: event.target.value as Tone['drama'] })}>
        {dramaChoices(intensity?.drama_world ?? 'uneasy').map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select>}
    </Field>
    <Field label="Lasting injuries" hint="Whether a maiming can leave a lost eye, a limp or a scar, and whether it stays.">
      {(id, describedBy) => <select id={id} value={rules.injury_persistence} aria-describedby={describedBy} onChange={(event) => onChange({ injury_persistence: event.target.value as InjuryPersistence })}>
        {INJURIES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select>}
    </Field>
  </>)
}

type Campaign = { arc: StoryArc | null; pace: StoryPace | null; ironman: boolean; legacy: Legacy | null }

/** What is chosen once for the whole campaign: how far and fast the character rises, Ironman, an earlier story. */
function CampaignFields({ choices, value, onChange }: { choices: StartChoices; value: Campaign; onChange: (value: Campaign) => void }) {
  const world = choices.arc
  return (<>
    {world && <div className="story-arc">
      <Field label="How far you can rise" hint="The work, foes and places that come to you grow with your name, up to this.">
        {(id, describedBy) => <select id={id} value={value.arc ?? world.arc} aria-describedby={describedBy} onChange={(event) => onChange({ ...value, arc: event.target.value as StoryArc })}>
          {(Object.entries(ARC_NAMES) as [StoryArc, string][]).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </select>}
      </Field>
      <Field label="How fast">
        {(id) => <select id={id} value={value.pace ?? world.pace} onChange={(event) => onChange({ ...value, pace: event.target.value as StoryPace })}>
          {(Object.entries(PACE_NAMES) as [StoryPace, string][]).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </select>}
      </Field>
    </div>}
    <Toggle label="Ironman" hint="No going back for this whole campaign: no earlier line, no other branch. If your character dies, the story ends there."
      checked={value.ironman} onChange={(checked) => onChange({ ...value, ironman: checked })} />
    <LegacyPick candidates={choices.legacy ?? []} value={value.legacy} onChange={(legacy) => onChange({ ...value, legacy })} />
  </>)
}

/** An earlier campaign's character, brought in as this world's history (dungeon/legacy.py). */
function LegacyPick({ candidates, value, onChange }: { candidates: LegacyCandidate[]; value: Legacy | null; onChange: (value: Legacy | null) => void }) {
  if (!candidates.length) return null
  const line = (item: LegacyCandidate) => `${item.name}, from ${item.world}${item.dead ? ' (died)' : ''}`
  return (
    <div className="story-arc">
      <Field label="An earlier story" hint="Bring a character from another world's story into this one, as history.">
        {(id, describedBy) => <select id={id} value={value?.world_id ?? ''} aria-describedby={describedBy}
          onChange={(event) => onChange(event.target.value ? { world_id: event.target.value, role: value?.role ?? 'legend' } : null)}>
          <option value="">None</option>
          {candidates.map((item) => <option key={item.world_id} value={item.world_id}>{line(item)}</option>)}
        </select>}
      </Field>
      {value && <Field label="They come back as">
        {(id) => <select id={id} value={value.role} onChange={(event) => onChange({ ...value, role: event.target.value as LegacyRole })}>
          {(Object.entries(LEGACY_ROLES) as [LegacyRole, string][]).map(([role, label]) => <option key={role} value={role}>{label}</option>)}
        </select>}
      </Field>}
    </div>
  )
}

function given(choices: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(Object.entries(choices).filter(([, value]) => value))
}
