import { useState, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api'
import type { BrpChoices, IronswornChoices, PersonaGender, Ruleset, Srd52Choices, Story as StoryData, StoryIntensity, StoryStart as StartChoices } from '../../types'
import { Field, TextArea, TextInput } from '../../components/Fields'
import { Stepper } from '../../components/NumberFields'
import { Loading, Notice } from '../../components/Feedback'
import { GENDERS } from '../worlds/worldsText'
import { WORLDS_KEY } from '../worlds/useWorlds'
import { arrayPlaced, brpCost, skillChoices, skillId, pointsLeft, pointsText, premadeLine, startingStats } from './storyText'
import { SessionZero } from './SessionZero'
import { FateBuild, type FateDraft } from './FateBuild'

/** Campaign start (dungeon/campaign.py): play a premade character from this town, or make your own; then session zero
 * (./SessionZero.tsx) sets how the campaign plays. The ruleset is picked first, as it decides how a character is made. */
export function StoryStart({ onStarted, intensity }: { onStarted: (data: StoryData) => void; intensity?: StoryIntensity }) {
  const choices = useQuery({ queryKey: ['story-start'], queryFn: () => api<StartChoices>('/story/start') })
  const client = useQueryClient()
  const [making, setMaking] = useState(false)
  const [who, setWho] = useState<{ name: string; body: object } | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [ruleset, setRuleset] = useState<Ruleset | null>(null)
  if (!choices.data) return <Loading label="Finding who you could be" />
  const begin = async (body: object) => {
    setBusy(true)
    setError('')
    try {
      onStarted(await api<StoryData>('/story/start', { ...who?.body, ...body, ...(ruleset ? { ruleset } : {}) }))
      await Promise.all([client.invalidateQueries({ queryKey: ['story-sheet'] }), client.invalidateQueries({ queryKey: WORLDS_KEY })])
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'The story did not start. Try again.') }
    finally { setBusy(false) }
  }
  if (who) return (<>
    <SessionZero choices={choices.data} intensity={intensity} ruleset={ruleset ?? choices.data.ruleset} who={who.name} busy={busy} onStart={(body) => void begin(body)} onBack={() => setWho(null)} />
    {error && <Notice tone="error">{error}</Notice>}
  </>)
  const { premades } = choices.data
  const own = making || !premades.length
  return (
    <section className="story-start" aria-labelledby="story-start-heading">
      <h2 id="story-start-heading">Who are you?</h2>
      <RulesetPick choices={choices.data} value={ruleset} onChange={setRuleset} />
      {!own && <>
        <p className="subtle">Play someone from this town, or make your own.</p>
        <ul className="story-premades">
          {premades.map((premade) => (
            <li key={premade.id}>
              <strong>{premade.name}</strong> <span className="subtle">{premadeLine(premade)}</span>
              <p>{premade.about}</p>
              <button type="button" className="button primary" onClick={() => setWho({ name: premade.name, body: { premade_id: premade.id } })}>Play as {premade.name.split(' ')[0]}</button>
            </li>
          ))}
        </ul>
        <button type="button" className="button" onClick={() => setMaking(true)}>Make your own…</button>
      </>}
      {own && <MakeYourOwn choices={choices.data} ruleset={ruleset ?? choices.data.ruleset} busy={busy} onBegin={(body, name) => setWho({ name, body })}
        onBack={premades.length ? () => setMaking(false) : undefined} />}
    </section>
  )
}

interface MakeProps { choices: StartChoices; ruleset?: Ruleset; busy: boolean; onBegin: (body: object, name: string) => void; onBack?: () => void }

function MakeYourOwn({ choices, ruleset, busy, onBegin, onBack }: MakeProps) {
  const [name, setName] = useState('')
  const [gender, setGender] = useState<PersonaGender>('')
  const [age, setAge] = useState('')
  const [about, setAbout] = useState('')
  const [stats, setStats] = useState(() => startingStats(choices))
  const [build, setBuild] = useState<Build | null>(null)
  const [iron, setIron] = useState<IronBuild | null>(null)
  const [percent, setPercent] = useState<PercentBuild | null>(() => choices.brp ? startingPercent(choices.brp) : null)
  const years = age ? Number(age) : null
  const kind = rulesKind(ruleset, choices)
  const [narrated, setNarrated] = useState({ good_at: '', bad_at: '' })
  const [fate, setFate] = useState<FateDraft | null>(null)
  const native = { srd52: build, ironsworn: iron, brp: percentReady(percent, choices.brp), narrative: listed(narrated), fate, marvel: true }[kind]
  const valid = !!name.trim() && builtFor(native, pointsLeft(stats, choices.points)) && adultAge(years)
  const sheetPart = kind === 'marvel' ? { stats } : { [BODY_KEYS[kind]]: native }
  const submit = () => onBegin({ persona: { name: name.trim(), gender, age: years, about: about.trim() }, ...sheetPart }, name.trim())
  return (
    <form className="story-make" onSubmit={(event) => { event.preventDefault(); if (valid) submit() }}>
      <TextInput label="Name" value={name} onChange={setName} required maxLength={80} />
      <label className="field">Gender
        <select value={gender} onChange={(event) => setGender(event.target.value as PersonaGender)}>
          {GENDERS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
      </label>
      <TextInput label="Age" type="number" value={age} onChange={setAge} min={18} max={120} />
      <TextArea label="About you" hint="Who they are, what they want, what they're running from. The narrator only knows what you write here."
        value={about} onChange={setAbout} rows={4} maxLength={2000} />
      <RulesBuild choices={choices} kind={kind} stats={stats} percent={percent} narrated={narrated} onStats={setStats} onBuild={setBuild} onIron={setIron} onPercent={setPercent} onNarrated={setNarrated} onFate={setFate} />
      <div className="form-actions">
        <button type="submit" className="button primary" disabled={busy || !valid}>Next: how it plays</button>
        {onBack && <button type="button" className="button" onClick={onBack}>Back</button>}
      </div>
    </form>
  )
}

/** Whether the made character's sheet is ready: a 5E or Ironsworn build chosen, else Prospero's points not overspent. */
function builtFor(build: unknown, left: number): boolean {
  return build === true ? left >= 0 : !!build
}

type RulesKind = 'marvel' | 'srd52' | 'ironsworn' | 'brp' | 'narrative' | 'fate'
/** Where each ruleset's build goes in the start request (dungeon/story_routes.py StoryStart). */
const BODY_KEYS: Record<Exclude<RulesKind, 'marvel'>, string> = { srd52: 'build', ironsworn: 'ironsworn', brp: 'brp', narrative: 'narrative', fate: 'fate' }
type Narrated = { good_at: string; bad_at: string }

/** A Narrative Only build: the two optional lists, typed as comma-separated words. */
function listed(narrated: Narrated): { good_at: string[]; bad_at: string[] } {
  const split = (text: string) => text.split(',').map((item) => item.trim()).filter(Boolean).slice(0, 6)
  return { good_at: split(narrated.good_at), bad_at: split(narrated.bad_at) }
}

/** The ruleset whose build the form shows: one the start choices carry, else Prospero. */
function rulesKind(ruleset: Ruleset | undefined, choices: StartChoices): RulesKind {
  return ruleset && ruleset !== 'marvel' && choices[ruleset] ? ruleset : 'marvel'
}

interface RulesBuildProps {
  choices: StartChoices; kind: RulesKind; stats: Record<string, number>; percent: PercentBuild | null; narrated: Narrated
  onStats: (stats: Record<string, number>) => void; onBuild: (build: Build | null) => void; onIron: (build: IronBuild | null) => void
  onPercent: (build: PercentBuild) => void; onNarrated: (narrated: Narrated) => void; onFate: (build: FateDraft | null) => void
}

/** The character's sheet in the campaign's ruleset. */
function RulesBuild({ choices, kind, stats, percent, narrated, onStats, onBuild, onIron, onPercent, onNarrated, onFate }: RulesBuildProps) {
  const own: Partial<Record<RulesKind, () => ReactNode>> = {
    fate: () => choices.fate && <FateBuild choices={choices.fate} onChange={onFate} />,
    narrative: () => choices.narrative && <NarrativeBuild narrated={narrated} onChange={onNarrated} />,
    srd52: () => choices.srd52 && <Srd52Build choices={choices.srd52} onChange={onBuild} />,
    ironsworn: () => choices.ironsworn && <IronswornBuild choices={choices.ironsworn} onChange={onIron} />,
    brp: () => choices.brp && percent && <PercentileBuild choices={choices.brp} build={percent} onChange={onPercent} />,
  }
  return own[kind]?.() || <MarvelStats choices={choices} stats={stats} onChange={onStats} />
}

/** Narrative Only (dungeon/rules/narrative.py): no stats to buy; About you is the sheet, and two optional lists sharpen it.
 *  The ruleset's own hint shows under the Rules pick (RulesetPick). */
function NarrativeBuild({ narrated, onChange }: { narrated: Narrated; onChange: (narrated: Narrated) => void }) {
  return <>
    <TextInput label="Good at (optional)" hint="A few things, separated by commas." value={narrated.good_at} maxLength={500} onChange={(good_at) => onChange({ ...narrated, good_at })} />
    <TextInput label="Bad at (optional)" hint="A few things, separated by commas." value={narrated.bad_at} maxLength={500} onChange={(bad_at) => onChange({ ...narrated, bad_at })} />
  </>
}

type PercentBuild = { characteristics: Record<string, number>; profession: string; personality: string }

function startingPercent(choices: BrpChoices): PercentBuild {
  return { characteristics: Object.fromEntries(choices.characteristics.map((item) => [item.id, choices.start])),
    profession: choices.professions[0].id, personality: choices.personalities[0].id }
}

function percentLeft(build: PercentBuild, choices: BrpChoices): number {
  return choices.points - brpCost(build.characteristics, choices.start, choices.costly, choices.costly_price)
}

/** The build, when its characteristics cost no more than the points. */
function percentReady(build: PercentBuild | null, choices: BrpChoices | undefined): PercentBuild | null {
  return build && choices && percentLeft(build, choices) >= 0 ? build : null
}

/** A Percentile character (dungeon/rules/brp.py build): characteristics bought from the points, a profession and a
 * personality; code spreads the skill points. */
function PercentileBuild({ choices, build, onChange: update }: { choices: BrpChoices; build: PercentBuild; onChange: (build: PercentBuild) => void }) {
  const left = percentLeft(build, choices)
  const [min, max] = choices.range
  const profession = choices.professions.find((item) => item.id === build.profession)
  return (
    <fieldset className="story-build">
      <legend>Your character</legend>
      <p className={left < 0 ? 'story-points over' : 'story-points'}>{left} of {choices.points} points left (DEX, INT and POW cost {choices.costly_price} a point).</p>
      <div className="story-stats">
        {choices.characteristics.map((item) => (
          <Stepper key={item.id} label={item.id.toUpperCase()} value={build.characteristics[item.id]} min={min} max={max} hint={item.name}
            format={String} onChange={(value) => update({ ...build, characteristics: { ...build.characteristics, [item.id]: value } })} />
        ))}
      </div>
      <Field label="Profession" hint={profession?.skills.join(', ')}>
        {(id, describedBy) => <select id={id} value={build.profession} aria-describedby={describedBy} onChange={(event) => update({ ...build, profession: event.target.value })}>
          {choices.professions.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>}
      </Field>
      <Field label="Personality" hint={choices.personalities.find((item) => item.id === build.personality)?.about}>
        {(id, describedBy) => <select id={id} value={build.personality} aria-describedby={describedBy} onChange={(event) => update({ ...build, personality: event.target.value })}>
          {choices.personalities.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>}
      </Field>
      <p className="subtle story-attribution">{choices.attribution}</p>
    </fieldset>
  )
}

type IronBuild = { stats: Record<string, number>; assets: string[] }

/** An Ironsworn character (dungeon/rules/ironsworn.py build): 3, 2, 2, 1 and 1 on the five stats, three assets. */
function IronswornBuild({ choices, onChange }: { choices: IronswornChoices; onChange: (build: IronBuild | null) => void }) {
  const [stats, setStats] = useState<Record<string, number>>(() => Object.fromEntries(choices.stats.map((stat, index) => [stat.id, choices.array[index]])))
  const [picks, setPicks] = useState<string[]>([])
  const report = (next: IronBuild) => onChange(arrayPlaced(next.stats, choices.array) && next.assets.length === choices.count ? next : null)
  const place = (stat: string, value: number) => { const next = { ...stats, [stat]: value }; setStats(next); report({ stats: next, assets: picks }) }
  const toggle = (asset: string) => {
    const next = picks.includes(asset) ? picks.filter((item) => item !== asset) : [...picks, asset].slice(-choices.count)
    setPicks(next)
    report({ stats, assets: next })
  }
  const categories = [...new Set(choices.assets.map((asset) => asset.category))]
  return (
    <fieldset className="story-build">
      <legend>Your Ironsworn character</legend>
      <p className="subtle">Place 3, 2, 2, 1 and 1, one on each stat.</p>
      <div className="story-abilities">
        {choices.stats.map((stat) => <label key={stat.id} className="field" title={stat.about}>{stat.name}
          <select value={stats[stat.id]} onChange={(event) => place(stat.id, Number(event.target.value))}>
            {[...new Set(choices.array)].map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
        </label>)}
      </div>
      {!arrayPlaced(stats, choices.array) && <p className="story-points over">Use 3 once, 2 twice and 1 twice.</p>}
      <p className="subtle">Choose {choices.count} assets ({picks.length} chosen).</p>
      {categories.map((category) => <details key={category}>
        <summary>{category}</summary>
        <div className="story-skills">
          {choices.assets.filter((asset) => asset.category === category).map((asset) => <label key={asset.id} className="checkbox" title={asset.about}>
            <input type="checkbox" checked={picks.includes(asset.id)} onChange={() => toggle(asset.id)} />{asset.name}
          </label>)}
        </div>
      </details>)}
      <p className="subtle story-attribution">{choices.attribution}</p>
    </fieldset>
  )
}

/** The ruleset the campaign is played in (dungeon/sheet.py): chosen now and locked for the whole campaign. */
function RulesetPick({ choices, value, onChange }: { choices: StartChoices; value: Ruleset | null; onChange: (value: Ruleset) => void }) {
  if (!choices.rulesets || choices.rulesets.length < 2) return null
  const current = value ?? choices.ruleset ?? 'marvel'
  return (<>
    <Field label="Rules" hint="How what your character tries is decided. Chosen now for the whole campaign; it cannot change later.">
      {(id, describedBy) => <select id={id} value={current} aria-describedby={describedBy} onChange={(event) => onChange(event.target.value as Ruleset)}>
        {choices.rulesets?.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
      </select>}
    </Field>
    {current === 'narrative' && choices.narrative && <p className="subtle">{choices.narrative.hint}</p>}
    {current === 'fate' && choices.fate && <p className="subtle">{choices.fate.hint}</p>}
  </>)
}

type Build = { class_id: string; species_id: string; background_id: string; scores: Record<string, number>; skills: string[] }

/** A 5E character (dungeon/rules/srd52.py build): class, species and background from the pack, the standard array
 * placed on the six abilities (the background then adds +2 and +1), and the class's skills. */
function Srd52Build({ choices, onChange }: { choices: Srd52Choices; onChange: (build: Build | null) => void }) {
  const [classId, setClassId] = useState(choices.classes[0].id)
  const [speciesId, setSpeciesId] = useState(choices.species[0].id)
  const [backgroundId, setBackgroundId] = useState(choices.backgrounds[0].id)
  const [scores, setScores] = useState<Record<string, number>>(() => Object.fromEntries(choices.abilities.map((ability, index) => [ability.id, choices.array[index]])))
  const [picks, setPicks] = useState<string[]>([])
  const chosen = choices.classes.find((item) => item.id === classId) ?? choices.classes[0]
  const background = choices.backgrounds.find((item) => item.id === backgroundId) ?? choices.backgrounds[0]
  const open = skillChoices(chosen.skills.from, background.skills)
  const report = (next: Partial<{ classId: string; speciesId: string; backgroundId: string; scores: Record<string, number>; picks: string[] }>) => {
    const build = { class_id: next.classId ?? classId, species_id: next.speciesId ?? speciesId, background_id: next.backgroundId ?? backgroundId, scores: next.scores ?? scores, skills: next.picks ?? picks }
    const count = choices.classes.find((item) => item.id === build.class_id)?.skills.count ?? 0
    onChange(arrayPlaced(build.scores, choices.array) && build.skills.length === count ? build : null)
  }
  const pickClass = (id: string) => { setClassId(id); setPicks([]); report({ classId: id, picks: [] }) }
  const pickBackground = (id: string) => { setBackgroundId(id); setPicks([]); report({ backgroundId: id, picks: [] }) }
  const place = (ability: string, value: number) => { const next = { ...scores, [ability]: value }; setScores(next); report({ scores: next }) }
  const toggle = (skill: string) => {
    const next = picks.includes(skill) ? picks.filter((item) => item !== skill) : [...picks, skill].slice(-chosen.skills.count)
    setPicks(next)
    report({ picks: next })
  }
  return (
    <fieldset className="story-build">
      <legend>Your 5E character</legend>
      <PackSelect label="Class" value={classId} items={choices.classes} onChange={pickClass} />
      <PackSelect label="Species" value={speciesId} items={choices.species} onChange={(id) => { setSpeciesId(id); report({ speciesId: id }) }} />
      <PackSelect label="Background" value={backgroundId} items={choices.backgrounds} onChange={pickBackground} />
      <p className="subtle">Place 15, 14, 13, 12, 10 and 8, one on each ability. {background.name} then adds +2 and +1 among {background.abilities.join(', ')}. {chosen.name}s lean on {chosen.primary}.</p>
      <div className="story-abilities">
        {choices.abilities.map((ability) => <label key={ability.id} className="field">{ability.name}
          <select value={scores[ability.id]} onChange={(event) => place(ability.id, Number(event.target.value))}>
            {choices.array.map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
        </label>)}
      </div>
      {!arrayPlaced(scores, choices.array) && <p className="story-points over">Use each number once.</p>}
      <p className="subtle">Pick {chosen.skills.count} skills ({background.name} gives {background.skills.join(' and ')}).</p>
      <div className="story-skills">
        {open.map((skill) => <label key={skill} className="checkbox">
          <input type="checkbox" checked={picks.includes(skillId(skill))} onChange={() => toggle(skillId(skill))} />{skill}
        </label>)}
      </div>
      <p className="subtle story-attribution">{choices.attribution}</p>
    </fieldset>
  )
}

function PackSelect({ label, value, items, onChange }: { label: string; value: string; items: { id: string; name: string }[]; onChange: (id: string) => void }) {
  return (
    <label className="field">{label}
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {items.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
      </select>
    </label>
  )
}

/** The start's optional choices, only those the player made. */
function adultAge(years: number | null): boolean {
  return years === null || (years >= 18 && years <= 120)
}

/** Prospero's stats bought from the pool of points (dungeon/campaign.py bought). */
function MarvelStats({ choices, stats, onChange }: { choices: StartChoices; stats: Record<string, number>; onChange: (stats: Record<string, number>) => void }) {
  const [min, max] = choices.range
  const left = pointsLeft(stats, choices.points)
  return <>
    <p className={left < 0 ? 'story-points over' : 'story-points'}>{pointsText(left, choices.points)}</p>
    <div className="story-stats">
      {choices.stat_names.map((stat) => (
        <Stepper key={stat} label={stat} value={stats[stat]} min={min} max={max} hint={choices.meanings[stat]}
          format={String} onChange={(value) => onChange({ ...stats, [stat]: value })} />
      ))}
    </div>
  </>
}
