import { useState } from 'react'
import type { DramaLevel, IntensityPreset, StoryIntensity as Intensity, TableRules, ToneVoice } from '../../types'
import { Field, Toggle } from '../../components/Fields'
import { Notice } from '../../components/Feedback'
import { dramaChoices, intensityChoices, LEVEL_NAMES, TONE_CATEGORIES, toggledVeil, VEIL_TOPICS, VOICES } from './storyText'
import { NarrationFormat } from './NarrationFormat'
import { useTable } from './table'
import { POLITICS_LEVELS } from './politicsText'

/** How far the story goes on the page (dungeon/story.py intensity) and how eventful it is (dungeon/happenings.py):
 * the world's own, or the player's, at any time; and whether off-page beats are shown (dungeon/beats.py). This
 * campaign's rules, kept at the Table (./table.ts). */
export function StoryIntensity({ intensity, onSaved }: { intensity: Intensity; onSaved: () => void }) {
  const { rules, save: keep } = useTable()
  const [error, setError] = useState('')
  const save = async (change: Partial<TableRules>) => {
    setError('')
    try { await keep(change); onSaved() }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'That setting was not saved.') }
  }
  return (<>
    <Field label="How far the story goes" hint="Violence, sex, horror, cruelty and drugs on the page. Change it whenever you like; the next line follows it.">
      {(id, describedBy) => <select id={id} value={intensity.chosen} aria-describedby={describedBy}
        onChange={(event) => void save({ intensity: event.target.value as IntensityPreset })}>
        {intensityChoices(intensity.world).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select>}
    </Field>
    <ToneDetails intensity={intensity} save={(change) => void save(change)} />
    {rules && <details className="tone-details">
      <summary>How it's written</summary>
      <NarrationFormat rules={rules} onChange={(change) => void save(change)} />
    </details>}
    <Field label="How eventful" hint="How often the world throws something at you: news, trouble, a stranger at the fire. It never changes the dice.">
      {(id, describedBy) => <select id={id} value={intensity.drama_chosen ?? 'world'} aria-describedby={describedBy}
        onChange={(event) => void save({ drama: event.target.value as DramaLevel })}>
        {dramaChoices(intensity.drama_world ?? 'uneasy').map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select>}
    </Field>
    {rules && <Toggle label="Shopkeepers' cash runs out" hint="On: a shop can only buy what its till can pay for, until it restocks. Off: shops always have the money."
      checked={rules.shop_cash !== 'unlimited'} onChange={(checked) => void save({ shop_cash: checked ? 'finite' : 'unlimited' })} />}
    {rules && <Toggle label="Carrying limits" hint="On: what you carry is counted in slots, more with Vitality. Off: carry anything."
      checked={rules.carry_limit !== 'off'} onChange={(checked) => void save({ carry_limit: checked ? 'slots' : 'off' })} />}
    {rules && <Field label="World clock" hint="Story time moves only as you play. Real time keeps the world moving while the app is closed: come back tomorrow and a day has passed.">
      {(id, describedBy) => <select id={id} value={rules.clock ?? 'world'} aria-describedby={describedBy}
        onChange={(event) => void save({ clock: event.target.value as TableRules['clock'] })}>
        <option value="world">As the world keeps it</option>
        <option value="story">Story time</option>
        <option value="real_time">Real time</option>
      </select>}
    </Field>}
    <LeavingRule rules={rules} save={(change) => void save(change)} />
    <PoliticsRule rules={rules} save={(change) => void save(change)} />
    {rules && ['ironsworn', 'srd52', 'brp'].includes(intensity.ruleset ?? '') && <Toggle label="Give the narrator rule text"
      hint="A few lines from the rules each turn, such as the move you rolled or a condition a foe took, so the story describes the result the way the rules mean it. The dice still decide."
      checked={rules.rule_text !== 'off'} onChange={(checked) => void save({ rule_text: checked ? 'on' : 'off' })} />}
    <Toggle label="Meanwhile cutaways" hint="Short scenes of what happens to the people you know while you are elsewhere. Your character still only learns it when word reaches them."
      checked={Boolean(intensity.cutaways)} onChange={(checked) => void save({ cutaways: checked })} />
    {intensity.ruleset === 'srd52' && <Toggle label="Foes decide a defeat" hint="Off: at 0 hit points the death saves decide, as written. On: only foes out to kill bring the death saves; others take what they came for, a prisoner, a purse or a beaten stranger thrown out."
      checked={intensity.defeat === 'by_aim'} onChange={(checked) => void save({ defeat: checked ? 'by_aim' : 'as_written' })} />}
    {error && <Notice tone="error">{error}</Notice>}
  </>)
}


/** Who can stop the character leaving a scene (dungeon/leaving.py): anyone with a reason, only a fight, or nobody. */
function LeavingRule({ rules, save }: { rules?: TableRules | null; save: (change: Partial<TableRules>) => void }) {
  if (!rules) return null
  return <Field label="Who can stop you leaving" hint="Anyone with a reason: someone there who hates you and isn't afraid of you blocks the way, someone fond of you begs you to stay, and a fight holds you until you flee. Each is a roll to get away. Only fights: conversations never hold you. Nobody: you can walk out of a fight too.">
    {(id, describedBy) => <select id={id} value={rules.leaving ?? 'anyone'} aria-describedby={describedBy}
      onChange={(event) => void save({ leaving: event.target.value as TableRules['leaving'] })}>
      <option value="anyone">Anyone with a reason</option>
      <option value="fights">Only fights</option>
      <option value="nobody">Nobody</option>
    </select>}
  </Field>
}

/** How much local politics goes on (dungeon/politics.py): the town's arguments, its factions and who takes which side. */
function PoliticsRule({ rules, save }: { rules?: TableRules | null; save: (change: Partial<TableRules>) => void }) {
  if (!rules) return null
  const value = rules.politics ?? 'true_to_life'
  return <Field label="Local politics" hint={`${POLITICS_LEVELS.find((level) => level.value === value)?.hint ?? ''} See it under More > Talk of the town.`}>
    {(id, describedBy) => <select id={id} value={value} aria-describedby={describedBy}
      onChange={(event) => void save({ politics: event.target.value as TableRules['politics'] })}>
      {POLITICS_LEVELS.map((level) => <option key={level.value} value={level.value}>{level.label}</option>)}
    </select>}
  </Field>
}

/** Each category on its own slider, the veils, and the narrator's voice (dungeon/tone.py). A preset above sets every
 *  category again; the veils and the voice stay. */
function ToneDetails({ intensity, save }: { intensity: Intensity; save: (change: Partial<TableRules>) => void }) {
  const levels = intensity.levels
  const veils = intensity.veils ?? []
  if (!levels) return null
  return (
    <details className="tone-details" open={intensity.custom || veils.length > 0}>
      <summary>Each kind on its own{intensity.custom ? ' (changed)' : ''}</summary>
      {TONE_CATEGORIES.map(([id, label]) => <Field key={id} label={`${label}: ${LEVEL_NAMES[levels[id]]}`}>
        {(fieldId) => <input id={fieldId} type="range" min={0} max={3} step={1} value={levels[id]}
          aria-valuetext={LEVEL_NAMES[levels[id]]} onChange={(event) => save({ levels: { ...levels, [id]: Number(event.target.value) } })} />}
      </Field>)}
      <fieldset className="tone-veils">
        <legend className="field-label">Veils</legend>
        <p className="subtle">These can still happen, but the page fades to black.</p>
        {VEIL_TOPICS.map(([id, label]) => <label key={id} className="checkbox-row">
          <input type="checkbox" checked={veils.includes(id)} onChange={(event) => save({ veils: toggledVeil(veils, id, event.target.checked) })} />
          {label}
        </label>)}
      </fieldset>
      <Field label="Voice" hint="How the narrator writes. It never changes the dice.">
        {(id, describedBy) => <select id={id} value={intensity.voice_chosen ?? 'world'} aria-describedby={describedBy}
          onChange={(event) => save({ voice: event.target.value as ToneVoice })}>
          <option value="world">The world's own</option>
          {VOICES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>}
      </Field>
    </details>
  )
}
