import type { LegacyCandidate, LegacyRole, StoryArc, StoryHand, StoryPace, StoryStart as StartChoices } from '../../types'
import { Field, Toggle } from '../../components/Fields'
import { ARC_NAMES, HAND_NAMES, LEGACY_ROLES, PACE_NAMES } from './storyText'
import type { Legacy, Session } from './campaignSession'

/** How hard the story pushes, how far the character can rise and how fast, Ironman and an earlier story. */
export function CampaignOptions({ choices, session }: { choices: StartChoices; session: Session }) {
  const { campaign: value, setCampaign: onChange } = session
  const world = choices.arc
  return (
    <details className="cast-options">
      <summary>Options</summary>
      {world && <>
        <Field label="How hard the story pushes">
          {(id) => <select id={id} value={session.steer} onChange={(event) => session.setHand(event.target.value as StoryHand)}>
            {(Object.entries(HAND_NAMES) as [StoryHand, string][]).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </select>}
        </Field>
        <div className="story-arc">
          <Field label="How far you can rise">
            {(id) => <select id={id} value={value.arc ?? world.arc} onChange={(event) => onChange({ ...value, arc: event.target.value as StoryArc })}>
              {(Object.entries(ARC_NAMES) as [StoryArc, string][]).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
            </select>}
          </Field>
          <Field label="How fast">
            {(id) => <select id={id} value={value.pace ?? world.pace} onChange={(event) => onChange({ ...value, pace: event.target.value as StoryPace })}>
              {(Object.entries(PACE_NAMES) as [StoryPace, string][]).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
            </select>}
          </Field>
        </div>
      </>}
      {/* Ironman can't be undone for the campaign, so it says what it costs. */}
      <Toggle label="Ironman" hint="No going back: if your character dies, the story ends there."
        checked={value.ironman} onChange={(checked) => onChange({ ...value, ironman: checked })} />
      <LegacyPick candidates={choices.legacy ?? []} value={value.legacy} onChange={(legacy) => onChange({ ...value, legacy })} />
    </details>
  )
}

/** An earlier campaign's character, brought in as this world's history (adventure/legacy.py). */
function LegacyPick({ candidates, value, onChange }: { candidates: LegacyCandidate[]; value: Legacy | null; onChange: (value: Legacy | null) => void }) {
  if (!candidates.length) return null
  const line = (item: LegacyCandidate) => `${item.name}, from ${item.world}${item.dead ? ' (died)' : ''}`
  return (
    <div className="story-arc">
      <Field label="An earlier story">
        {(id) => <select id={id} value={value?.world_id ?? ''}
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
