import { useState } from 'react'
import type { FateChoices } from '../../types'
import { TextInput } from '../../components/Fields'
import { arrayPlaced, signed } from './storyText'

export type FateDraft = { high_concept: string; trouble: string; aspects: string[]; approaches: Record<string, number>; stunts: string[] }

/** A Fate character (dungeon/rules/fate.py build): a high concept and a trouble, a few more aspects, the approaches'
 *  array placed, and stunts, all in the player's own words. Ready when there is a high concept and the array fits. */
export function FateBuild({ choices, onChange }: { choices: FateChoices; onChange: (build: FateDraft | null) => void }) {
  const [draft, setDraft] = useState<FateDraft>(() => ({
    high_concept: '', trouble: '', aspects: Array(choices.most_aspects).fill(''), stunts: Array(choices.most_stunts).fill(''),
    approaches: Object.fromEntries(choices.approaches.map((name, index) => [name, choices.array[index]])),
  }))
  const update = (change: Partial<FateDraft>) => {
    const next = { ...draft, ...change }
    setDraft(next)
    const lines = (items: string[]) => items.map((item) => item.trim()).filter(Boolean)
    onChange(next.high_concept.trim() && arrayPlaced(next.approaches, choices.array)
      ? { ...next, high_concept: next.high_concept.trim(), trouble: next.trouble.trim(), aspects: lines(next.aspects), stunts: lines(next.stunts) } : null)
  }
  const line = (key: 'aspects' | 'stunts', index: number, value: string) => update({ [key]: draft[key].map((item, at) => at === index ? value : item) })
  return (
    <fieldset className="story-build">
      <legend>Your Fate character</legend>
      <TextInput label="High concept" hint="Who they are in a few words: “Dockside cutpurse with a conscience”." value={draft.high_concept} required maxLength={120} onChange={(high_concept) => update({ high_concept })} />
      <TextInput label="Trouble" hint="What keeps going wrong for them: “Owes the Hollins gang”." value={draft.trouble} maxLength={120} onChange={(trouble) => update({ trouble })} />
      {draft.aspects.map((aspect, index) => <TextInput key={`aspect-${index}`} label={`Aspect ${index + 1} (optional)`} value={aspect} maxLength={120} onChange={(value) => line('aspects', index, value)} />)}
      <p className="subtle">Place {choices.array.map(signed).join(', ')} on the approaches, one each.</p>
      <div className="story-abilities">
        {choices.approaches.map((name) => <label key={name} className="field">{name}
          <select value={draft.approaches[name]} onChange={(event) => update({ approaches: { ...draft.approaches, [name]: Number(event.target.value) } })}>
            {[...new Set(choices.array)].map((value) => <option key={value} value={value}>{signed(value)}</option>)}
          </select>
        </label>)}
      </div>
      {!arrayPlaced(draft.approaches, choices.array) && <p className="story-points over">Use each of {choices.array.map(signed).join(', ')} once.</p>}
      {draft.stunts.map((stunt, index) => <TextInput key={`stunt-${index}`} label={`Stunt ${index + 1} (optional)`} hint={index === 0 ? 'Because I…, I get +2 when I… (it helps when the words fit what you try).' : undefined}
        value={stunt} maxLength={120} onChange={(value) => line('stunts', index, value)} />)}
      <p className="subtle story-attribution">{choices.attribution}</p>
    </fieldset>
  )
}
