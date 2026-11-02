import { useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api'
import type { Gear, Story, StoryPerson } from '../../types'
import { useWorlds } from '../worlds/useWorlds'
import { initial, personaName } from '../worlds/worldsText'
import { EntityName } from './EntityCard'
import { StoryGear } from './StoryGear'
import { peopleHere } from './scene'
import { aroundText, moneyText, personLine, statusItems } from './storyText'
import { MindBadge, MindToggle } from '../round/MindBadge'
import { RoundTimeline } from '../round/RoundTimeline'
import { hasAgents, liveSummary, modeOf, seatLine, seatOf, type CastRound } from '../round/round'

export type { CastRound }

/** Who's here, at the top of the scene panel: your character first, then the people met who are here. A row opens to
 *  show more: yours how you stand and your pack, theirs who they are to you and whether they think for themselves.
 *  Under them, who else is around and the weather. The scene line above the story has the place, the time and your
 *  condition. Once anyone thinks for themselves, the round timeline sits on top and each row says how that character
 *  is getting on this turn (src/features/round/). */
export function StoryCast({ story, round, onTrade }: { story: Story; round?: CastRound; onTrade: () => void }) {
  const persona = useWorlds().data?.persona
  const gear = useQuery({ queryKey: ['story-gear'], queryFn: () => api<Gear>('/story/gear'), enabled: story.messages.length > 0 })
  const [open, setOpen] = useState<string | null>(null)
  const coin = gear.data ? moneyText(gear.data.coins, gear.data.currency) : null
  const you = statusItems(story.scene, story.fight, coin).filter((item) => item.kind !== 'time').map((item) => item.text).join(' · ')
  const toggle = (key: string) => setOpen(open === key ? null : key)
  return (
    <section className="story-cast" aria-label="Who's here">
      {round && <CastTimeline round={round} />}
      <ul>
        <CastRow id="you" name={personaName(persona) || 'You'} letter={initial(persona) || 'Y'} state="You" open={open === 'you'} onToggle={toggle}>
          <p>{you}</p>
          <StoryGear open onTrade={onTrade} />
        </CastRow>
        {peopleHere(story).map((person) => round
          ? <CastPerson key={person.key} person={person} round={round} open={open === person.key} onToggle={toggle} />
          : <CastRow key={person.key} id={person.key} name={person.name} letter={person.name.charAt(0)} state={person.doing} open={open === person.key} onToggle={toggle}>
            <PersonMore person={person} />
          </CastRow>)}
      </ul>
      {!!story.scene.around.length && <p className="story-cast-around">{aroundText(story.scene.around)}</p>}
      {story.scene.weather && <p className="story-cast-around">{story.scene.weather}</p>}
    </section>
  )
}

/** Once anyone at the table thinks for themselves: the round timeline, with its summary for screen readers. */
function CastTimeline({ round }: { round: CastRound }) {
  if (!hasAgents(round.table)) return null
  return <RoundTimeline state={round.live.state ?? round.table?.under_way?.state ?? null} summary={liveSummary(round.live, round.table, round.waiting)} />
}

/** A character here as the round loop sees them: how they're getting on this turn in place of what they're doing, the
 *  Thinks or Rules badge once anyone thinks, and the choice between them when the row is open. */
function CastPerson({ person, round, open, onToggle }: { person: StoryPerson; round: CastRound; open: boolean; onToggle: (id: string) => void }) {
  const mind = seatOf(round.table, person.key)?.mind ?? 'program'
  const now = seatLine(person.key, round.live, modeOf(round.table), round.waiting)
  return (
    <CastRow id={person.key} name={person.name} letter={person.name.charAt(0)} state={now ?? person.doing}
      badge={hasAgents(round.table) && <MindBadge mind={mind} />} open={open} onToggle={onToggle}>
      <PersonMore person={person} />
      <MindToggle id={person.key} name={person.name} mind={mind} onChange={(next) => round.onMind(person, next)} />
    </CastRow>
  )
}

interface RowProps { id: string; name: string; letter: string; state: string; badge?: ReactNode; open: boolean; onToggle: (id: string) => void; children: ReactNode }

function CastRow({ id, name, letter, state, badge, open, onToggle, children }: RowProps) {
  return (
    <li>
      <button type="button" className="story-cast-row" aria-expanded={open} onClick={() => onToggle(id)}>
        <span className="portrait" aria-hidden="true">{letter}</span>
        <span className="story-cast-text"><span className="story-cast-name">{name}</span><span className="story-cast-state">{state}</span></span>
        {badge}
      </button>
      {open && <div className="story-cast-more">{children}</div>}
    </li>
  )
}

function PersonMore({ person }: { person: StoryPerson }) {
  return <>
    <p><EntityName entity={{ kind: 'person', key: person.key }}>{person.role}, {person.city}</EntityName></p>
    <p>{personLine(person)}</p>
    {person.bond && <p>Bonded to you ({person.bond})</p>}
    {person.feelings && <p>{person.feelings}</p>}
    {person.notes.length > 0 && <p className="story-note">{person.notes[person.notes.length - 1]}</p>}
  </>
}
