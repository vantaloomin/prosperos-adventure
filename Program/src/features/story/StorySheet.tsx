import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api'
import type { BrpSheet, FateSheet, IronswornSheet, MarvelSheet, NarrativeSheet, Sheet, SheetGrowth, Srd52Sheet, Srd52Spells } from '../../types'
import { Stepper } from '../../components/NumberFields'
import { Notice } from '../../components/Feedback'
import { abilityLine, bondLine, bondsText, darkText, signed, spellLine, xpLine } from './storyText'

const SHEET_KEY = ['story-sheet']

/** Your character in the campaign's ruleset (dungeon/sheet.py): Prospero's stats, each rolling a bigger die as it
 * grows, one used under pressure marked to grow at the next rest (dungeon/growth.py); or a 5E sheet. And the dark
 * tracks they are on. */
export function StorySheet({ open }: { open?: boolean }) {
  const sheet = useQuery({ queryKey: SHEET_KEY, queryFn: () => api<Sheet>('/story/sheet') })
  if (!sheet.data) return null
  return (
    <details className="story-sheet" open={open}>
      <summary>Your character</summary>
      <Rules sheet={sheet.data} />
      <Dark growth={sheet.data.growth} />
    </details>
  )
}

function Rules({ sheet }: { sheet: Sheet }) {
  if (sheet.ruleset === 'srd52') return <Srd52 sheet={sheet} />
  if (sheet.ruleset === 'ironsworn') return <Ironsworn sheet={sheet} />
  if (sheet.ruleset === 'brp') return <Percentile sheet={sheet} />
  if (sheet.ruleset === 'narrative') return <Narrative sheet={sheet} />
  if (sheet.ruleset === 'fate') return <Fate sheet={sheet} />
  return <Marvel sheet={sheet} />
}

/** A Narrative Only sheet (dungeon/rules/narrative.py): no stats; who the character is decides what happens. */
function Narrative({ sheet }: { sheet: NarrativeSheet }) {
  return <>
    <p className="subtle">No stats or dice: what happens comes from who your character is and what you write.</p>
    {!!sheet.good_at.length && <p>Good at: {sheet.good_at.join(', ')}</p>}
    {!!sheet.bad_at.length && <p>Bad at: {sheet.bad_at.join(', ')}</p>}
  </>
}

/** A Fate sheet (dungeon/rules/fate.py): the aspects and stunts in the player's words, approaches, Fate points spent
 *  and gained by code as the story goes, stress and consequences. */
function Fate({ sheet }: { sheet: FateSheet }) {
  const hurt = Object.entries(sheet.consequences).filter(([, text]) => text)
  return <>
    <p><strong>{sheet.high_concept}</strong>{sheet.trouble && <><br /><span className="subtle">Trouble:</span> {sheet.trouble}</>}</p>
    {!!sheet.aspects.length && <p>{sheet.aspects.join(' · ')}</p>}
    <p>{Object.entries(sheet.approaches).sort(([, a], [, b]) => b - a).map(([name, value]) => `${name} ${signed(value)}`).join(' · ')}</p>
    <p>Fate points {sheet.fate_points} (refresh {sheet.refresh}) · Stress {sheet.stress.map((marked) => marked ? '☒' : '☐').join('')}</p>
    {!!hurt.length && <p className="subtle">{hurt.map(([kind, text]) => `${kind}: ${text}`).join(' · ')}</p>}
    {!!sheet.stunts.length && <ul className="story-stunts">{sheet.stunts.map((stunt) => <li key={stunt}>{stunt}</li>)}</ul>}
    <p className="subtle story-attribution">{sheet.attribution}</p>
  </>
}

/** A Percentile sheet (dungeon/rules/brp.py): set when the character was made; skills grow by experience. */
function Percentile({ sheet }: { sheet: BrpSheet }) {
  return <>
    <p>{sheet.names.profession}, {sheet.names.personality.toLowerCase()}</p>
    <p>{Object.entries(sheet.characteristics).map(([stat, value]) => `${stat.toUpperCase()} ${value}`).join(' · ')}</p>
    <p>Hit points {Math.max(0, sheet.hp)} of {sheet.max_hp} (major wound {sheet.major_wound}) · Damage {sheet.damage_modifier} · Armour {sheet.armor_name} ({sheet.armor_value})</p>
    <p className="subtle">{Object.entries(sheet.rolls).map(([roll, value]) => `${roll} ${value}%`).join(' · ')}</p>
    {!!sheet.major_wounds.length && <p className="subtle">{sheet.major_wounds.map((wound) => wound.text).join(' ')}</p>}
    <details>
      <summary>Skills</summary>
      <p>{sheet.skill_list.filter((skill) => skill.value > 0).map((skill) => `${skill.name} ${skill.value}%${skill.checked ? ' •' : ''}`).join(' · ')}</p>
      <p className="subtle">• an experience check, rolled after a night's rest.</p>
    </details>
    {!!sheet.spell_list?.length && <details>
      <summary>Spells (power points {sheet.pp} of {sheet.max_pp}, up to level {sheet.most_level})</summary>
      {sheet.spell_list.map((spell) => <p key={spell.id}><strong>{spell.name} {spell.value}%{spell.checked ? ' •' : ''}</strong> <span className="subtle">({spell.cost} a level)</span> {spell.summary}</p>)}
    </details>}
    <p className="subtle story-attribution">{sheet.attribution}</p>
  </>
}

/** An Ironsworn sheet (dungeon/rules/ironsworn.py): set when the character was made, so it only reads. */
function progressLine(track: NonNullable<IronswornSheet['progress']>[number]) {
  const ticks = track.ticks % 4
  const name = track.rank ? `${track.name} (${track.rank})` : track.name
  return `${name}: progress ${track.boxes} of ${track.of}${ticks ? `, ${ticks} tick${ticks === 1 ? '' : 's'}` : ''}`
}

function Ironsworn({ sheet }: { sheet: IronswornSheet }) {
  return <>
    <p>{Object.entries(sheet.stats).map(([stat, value]) => `${stat} ${value}`).join(' · ')}</p>
    <p>Health {sheet.health} · Spirit {sheet.spirit} · Supply {sheet.supply} · Momentum {signed(sheet.momentum)} (max {sheet.momentum_max}, reset {sheet.momentum_reset}) · Experience {sheet.xp}</p>
    {!!sheet.debilities.length && <p className="subtle">{sheet.debilities.join(', ')}</p>}
    {sheet.progress?.map((track) => <p key={track.name}>{progressLine(track)}</p>)}
    <details>
      <summary>Assets</summary>
      {sheet.asset_list.map((asset) => <p key={asset.id}><strong>{asset.name}</strong> <span className="subtle">({asset.category})</span> {asset.abilities.join(' ')}</p>)}
    </details>
    <p className="subtle story-attribution">{sheet.attribution}</p>
  </>
}

function Marvel({ sheet }: { sheet: MarvelSheet }) {
  const client = useQueryClient()
  const [error, setError] = useState('')
  const [min, max] = sheet.range
  const growth = sheet.growth
  const save = async (stat: string, value: number) => {
    setError('')
    try { client.setQueryData(SHEET_KEY, await api<Sheet>('/story/sheet', { stats: { [stat]: value } }, 'PUT')) }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'That was not saved.') }
  }
  return <>
    <div className="story-stats">
      {sheet.stat_names.map((stat) => (
        <Stepper key={stat} label={growth?.marked.includes(stat) ? `${stat} •` : stat} value={sheet.stats[stat]} min={min} max={max}
          format={(value) => `${value} (d${sheet.dice[stat]})`} onChange={(value) => void save(stat, value)} />
      ))}
    </div>
    {!!growth?.marked.length && <p className="subtle">• Used under pressure: may grow at the next night's rest.</p>}
    {error && <Notice tone="error">{error}</Notice>}
  </>
}

/** A 5E sheet (dungeon/rules/srd52.py): set when the character was made, so it only reads. */
function Srd52({ sheet }: { sheet: Srd52Sheet }) {
  const skills = Object.entries(sheet.skill_bonuses)
  return <>
    <p><strong>Level {sheet.level} {sheet.names.species} {sheet.names.class}{sheet.names.subclass ? `, ${sheet.names.subclass}` : ''}</strong> <span className="subtle">({sheet.names.background})</span></p>
    <p className="subtle">{xpLine(sheet.level, sheet.xp, sheet.next_xp)}</p>
    <p>Hit points {sheet.hp} of {sheet.max_hp} · Armor Class {sheet.ac} · Speed {sheet.speed} ft. · Proficiency {signed(sheet.proficiency)}</p>
    <ul className="story-abilities" aria-label="Abilities">
      {Object.entries(sheet.abilities).map(([ability, score]) => <li key={ability}>{abilityLine(ability, score, sheet.modifiers[ability], sheet.saves.includes(ability))}</li>)}
    </ul>
    <details>
      <summary>Skills</summary>
      <ul className="story-skills">
        {skills.map(([id, skill]) => <li key={id} className={skill.proficient ? 'proficient' : undefined}>{skill.name} {signed(skill.bonus)}{skill.proficient ? ' •' : ''}</li>)}
      </ul>
      <p className="subtle">• Proficient.</p>
    </details>
    {!!sheet.features?.length && <details><summary>Features</summary><p>{sheet.features.join(', ')}</p></details>}
    {sheet.spell_list && <Spells spells={sheet.spell_list} />}
    <p className="subtle story-attribution">{sheet.attribution}</p>
  </>
}

function Spells({ spells }: { spells: Srd52Spells }) {
  return (
    <details>
      <summary>Spells</summary>
      <p>{spellLine(spells)}</p>
      {!!spells.cantrips.length && <p>Cantrips: {spells.cantrips.join(', ')}</p>}
      <p>Prepared: {spells.prepared.map((spell) => `${spell.name} (${spell.level})`).join(', ')}</p>
      <p className="subtle">Name a spell in your line to cast it.</p>
    </details>
  )
}

function Dark({ growth }: { growth?: SheetGrowth }) {
  const bonds = growth?.bonds
  return (
    <>
      {bonds && <p><strong>{bondsText(bonds)}</strong>{!!bonds.bonds.length && <span className="subtle"> {bonds.bonds.map(bondLine).join(', ')}</span>}</p>}
      {growth?.dark.map((track) => <p key={track.id}><strong>{darkText(track)}</strong>{track.changes.map((change) => <span key={change} className="subtle"> {change}</span>)}</p>)}
    </>
  )
}
