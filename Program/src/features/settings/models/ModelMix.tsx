// The narrator's Mix, adapted from Prospero's Companion src/features/settings/models/ModelMix.tsx (#441).
import { api } from '../../../api'
import { Toggle } from '../../../components/Fields'
import { isText, type ModelsOverview, type ModelMix as Mix } from './types'

const OFF: Mix = { enabled: false, mode: 'random', profile_ids: [] }

/** The narrator's own profile and one other: a mix that works the moment it is turned on. */
function starter(story: string | undefined, ids: string[]) {
  return [...(story && ids.includes(story) ? [story] : []), ...ids.filter(id => id !== story)].slice(0, 2)
}

/** Mix models for the narrator: each turn's narration comes from one of the chosen profiles, at random or in turn,
 * with that profile's own model and settings. Off by default; with fewer than two finished profiles the narrator's
 * profile tells the story. */
export function ModelMix({ overview, onChanged, onError }: { overview: ModelsOverview; onChanged: (data?: ModelsOverview) => void; onError: (text: string) => void }) {
  const mix = overview.mix?.story ?? OFF
  const ready = overview.profiles.filter(profile => profile.ready && isText(profile.config))
  if (ready.length < 2) return null
  const save = async (change: Partial<Mix>) => {
    const next = { ...mix, ...change }
    // Turning it on with nothing picked starts from the narrator's profile and the newest other one.
    if (next.enabled && !next.profile_ids.length) next.profile_ids = starter(overview.routes.story ?? overview.routes.chat, ready.map(profile => profile.id))
    try { onChanged(await api<ModelsOverview>('/models/mix', { job: 'story', ...next }, 'PUT')) } catch (error) { onError(error instanceof Error ? error.message : 'Not changed.') }
  }
  const toggle = (id: string, on: boolean) => void save({ profile_ids: on ? [...mix.profile_ids, id] : mix.profile_ids.filter(item => item !== id) })
  const safeOnly = ready.filter(profile => mix.profile_ids.includes(profile.id) && profile.config.provider === 'claude_code')
  return <div className="model-mix">
    <Toggle label="Mix narrator models" checked={mix.enabled} onChange={value => void save({ enabled: value })} hint="Each turn is told by one of the profiles you pick, with that profile's own model and settings, for more variety in the prose. The Referee and every other job keep their own profile." />
    {mix.enabled && <div className="model-mix-options form-stack">
      <fieldset className="plain-fieldset"><legend className="field-label">Profiles in the mix</legend>
        {ready.map(profile => <label key={profile.id} className="checkbox-row"><input type="checkbox" checked={mix.profile_ids.includes(profile.id)} onChange={event => toggle(profile.id, event.target.checked)} />{profile.name}</label>)}
        {mix.profile_ids.length < 2 && <small>Pick at least two. Until then the Story narrator profile tells the story.</small>}
        {safeOnly.length > 0 && <small>{safeOnly.map(profile => profile.name).join(', ')} won’t write the adult side of life, so those turns stay non-explicit.</small>}
      </fieldset>
      <fieldset className="plain-fieldset"><legend className="field-label">Order</legend>
        <div className="segmented">
          {([['random', 'At random'], ['in_turn', 'In turn']] as const).map(([value, label]) => <label key={value}>
            <input type="radio" className="visually-hidden" name="model-mix-mode" value={value} checked={mix.mode === value} onChange={() => void save({ mode: value })} /><span>{label}</span>
          </label>)}
        </div>
        <small>At random can repeat a model. In turn goes through them one after another.</small>
      </fieldset>
    </div>}
  </div>
}
