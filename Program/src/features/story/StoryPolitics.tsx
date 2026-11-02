import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { api } from '../../api'
import { reducedMotion } from '../../motion'
import type { PoliticsFaction, PoliticsIssue, PoliticsPerson, PoliticsView, TownPolitics } from '../../types'
import { Notice } from '../../components/Feedback'
import { ErrorNotice } from '../../components/ErrorNotice'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import {
  STAGE_CHOICES, STANCES, alliesText, backingText, beatDate, neitherText, outcomeChoices, outcomeText, pullText,
  relationsOf, sortedPeople, splitShares, splitText, stageLabel, viewLabel, viewOptions,
} from './politicsText'

const FACTIONS_SHOWN = 5
type Save = (path: string, body?: unknown, method?: string) => Promise<boolean>
interface Props {
  /** The town and the story's day, so the talk is fetched again when either moves on. */
  where: string
  /** With the GM view on, anything here can be changed. */
  gm: boolean
  open?: boolean
}

function useSave(key: unknown[]): { save: Save; error: string } {
  const client = useQueryClient()
  const [error, setError] = useState('')
  const save: Save = async (path, body, method) => {
    setError('')
    try {
      client.setQueryData(key, await api<TownPolitics>(`/story/politics${path}`, body, method))
      return true
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'That could not be saved.')
      return false
    }
  }
  return { save, error }
}

/** An editor that has just opened scrolls into view and puts the cursor in its first field. */
function useOpened<T extends HTMLElement>() {
  const box = useRef<T>(null)
  useEffect(() => {
    box.current?.scrollIntoView({ block: 'nearest', behavior: reducedMotion() ? 'auto' : 'smooth' })
    box.current?.querySelector<HTMLElement>('input, select')?.focus({ preventScroll: true })
  }, [])
  return box
}

/** Talk of the town (dungeon/politics.py): what people in the town argue about, the factions behind each side (the
 *  world's powers that hold it first) and where the people the character has met here stand. The game decides all
 *  of it; with the GM view on, anything can be changed. */
export function StoryPolitics({ where, gm, open }: Props) {
  const key = ['story-politics', where]
  const town = useQuery({ queryKey: key, queryFn: () => api<TownPolitics>('/story/politics') })
  const { save, error } = useSave(key)
  if (town.isError) return <ErrorNotice error={town.error} />
  const data = town.data
  if (!data || data.level === 0) return null
  return (
    <details className="story-people politics" open={open}>
      <summary>Talk of the town · {data.city.name}</summary>
      <p className="subtle">What people in {data.city.name} are arguing about, and where the people you have met stand.{gm ? ' Change anything here.' : ''}</p>
      {error && <Notice tone="error">{error}</Notice>}
      {data.issues.length > 0
        ? <ul className="politics-list">{data.issues.map((issue) => <IssueItem key={issue.id} issue={issue} data={data} gm={gm} save={save} />)}</ul>
        : <p className="subtle">Nothing much is being argued about right now.</p>}
      {gm && <AddIssue save={save} />}
      <Factions data={data} gm={gm} save={save} />
    </details>
  )
}

function IssueItem({ issue, data, gm, save }: { issue: PoliticsIssue; data: TownPolitics; gm: boolean; save: Save }) {
  const [open, setOpen] = useState(false)
  const latest = issue.beats[issue.beats.length - 1]
  const outcome = outcomeText(issue)
  return (
    <li className="politics-issue">
      <p className="politics-title"><strong>{issue.title}</strong> <span className="badge">{stageLabel(issue)}</span></p>
      {issue.question && <p className="subtle">{issue.question}</p>}
      <SplitBar issue={issue} />
      {outcome ? <p>{outcome}</p> : latest && <p className="subtle">Latest ({beatDate(latest.on)}): {latest.text}</p>}
      <button type="button" className="text-button" aria-expanded={open} onClick={() => setOpen((value) => !value)}>{open ? 'Less' : 'More'}</button>
      {open && <IssueDetail issue={issue} data={data} gm={gm} save={save} />}
    </li>
  )
}

/** How the town splits: each side's share at its end of the bar, those who don't much care under it. */
function SplitBar({ issue }: { issue: PoliticsIssue }) {
  const shares = splitShares(issue.split)
  return (
    <div className="politics-split">
      <div className="politics-split-ends" aria-hidden="true">
        <span><span className="politics-split-name">{issue.sides[0].name}</span> {shares.first}%</span>
        <span><span className="politics-split-name">{issue.sides[1].name}</span> {shares.second}%</span>
      </div>
      <div className="politics-split-bar" role="img" aria-label={splitText(issue)}>
        <span className="politics-split-first" style={{ width: `${shares.first}%` }} />
        <span className="politics-split-neither" style={{ width: `${shares.neither}%` }} />
        <span className="politics-split-second" style={{ width: `${shares.second}%` }} />
      </div>
      <p className="subtle" aria-hidden="true">{neitherText(issue.split)}</p>
    </div>
  )
}

function IssueDetail({ issue, data, gm, save }: { issue: PoliticsIssue; data: TownPolitics; gm: boolean; save: Save }) {
  const backing = backingText(issue, data.factions)
  return (
    <div className="politics-detail">
      {issue.beats.length > 1 && <ul className="plain-list">
        {issue.beats.map((beat) => <li key={beat.on + beat.text} className="subtle">{beatDate(beat.on)}: {beat.text}</li>)}
      </ul>}
      {backing.map((line) => <p key={line} className="subtle">{line}</p>)}
      <Odds issue={issue} />
      <People issue={issue} people={data.people} gm={gm} save={save} />
      {gm && <IssueEdit issue={issue} save={save} />}
    </div>
  )
}

/** The people met here, strongest views first; more than three who don't much care fold behind one button. */
function People({ issue, people, gm, save }: { issue: PoliticsIssue; people: PoliticsPerson[]; gm: boolean; save: Save }) {
  const [all, setAll] = useState(false)
  if (people.length === 0) return null
  const { shown, folded } = sortedPeople(people, issue.id)
  const rows = all ? [...shown, ...folded] : shown
  return (<>
    <h3 className="politics-subhead">People you have met</h3>
    <div className="politics-people">
      {rows.map((person) => <ViewRow key={person.key} issue={issue} person={person} view={person.views[issue.id]} gm={gm} save={save} />)}
    </div>
    {folded.length > 0 && !all && <p><button type="button" className="text-button" onClick={() => setAll(true)}>{folded.length} more don't much care</button></p>}
  </>)
}

/** Someone's view: words, or with the GM view a select, where "Let the game decide" hands it back. */
function ViewRow({ issue, person, view, gm, save }: { issue: PoliticsIssue; person: PoliticsPerson; view?: PoliticsView; gm: boolean; save: Save }) {
  const id = `view-${issue.id}-${person.key}`
  const mine = view?.by === 'you'
  const who = <>{person.name}{person.role && <span className="subtle"> ({person.role})</span>}{mine && <span className="subtle"> · you set this</span>}</>
  if (!gm) return <><span>{who}</span><span className="subtle">{viewLabel(view?.view ?? 0, issue)}</span></>
  const change = (picked: string) => void save('/views', { issue: issue.id, person: person.key, view: picked === 'game' ? null : Number(picked) }, 'PUT')
  return (<>
    <label htmlFor={id}>{who}</label>
    <select id={id} value={view ? String(view.view) : '0'} onChange={(event) => change(event.target.value)}>
      {viewOptions(issue).map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
      {mine && <option value="game">Let the game decide</option>}
    </select>
  </>)
}

/** With the odds shown: how likely each way was, and why. */
function Odds({ issue }: { issue: PoliticsIssue }) {
  const settled = issue.settled
  if (!settled || settled.options.every((option) => option.odds === undefined)) return null
  return (
    <ul className="plain-list">
      {settled.options.map((option) => (
        <li key={option.option}>
          <p><strong>{Math.round((option.odds ?? 0) * 100)}%</strong> {option.label}{option.option === settled.picked && <span className="subtle"> (what happened)</span>}</p>
          {!!option.reasons?.length && <p className="subtle">{option.reasons.join('; ')}.</p>}
        </li>
      ))}
    </ul>
  )
}

function IssueEdit({ issue, save }: { issue: PoliticsIssue; save: Save }) {
  const [editing, setEditing] = useState(false)
  if (!editing) return <p><button type="button" className="text-button" onClick={() => setEditing(true)}>Change this issue</button></p>
  return <IssueForm issue={issue} save={save} close={() => setEditing(false)} />
}

/** Rename it, its question or its sides, say how far a local issue has got or how it went, or put it away. */
function IssueForm({ issue, save, close }: { issue: PoliticsIssue; save: Save; close: () => void }) {
  const box = useOpened<HTMLFormElement>()
  const [title, setTitle] = useState(issue.title)
  const [question, setQuestion] = useState(issue.question)
  const [sides, setSides] = useState(issue.sides.map((side) => side.name))
  const [confirming, setConfirming] = useState(false)
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (await save(`/issues/${encodeURIComponent(issue.id)}`, { title: title.trim(), question: question.trim(), sides: sides.map((side) => side.trim()) }, 'PATCH')) close()
  }
  return (
    <form ref={box} className="politics-form" onSubmit={(event) => void submit(event)} aria-label={`Change ${issue.title}`}>
      <Text id={`title-${issue.id}`} label="What it's about" value={title} onChange={setTitle} />
      <Text id={`question-${issue.id}`} label="The question people argue over" value={question} onChange={setQuestion} required={false} max={200} />
      {sides.map((side, index) => <Text key={index} id={`side-${issue.id}-${index}`} label={index ? 'The other side' : 'One side'} value={side} onChange={(value) => setSides(sides.map((item, at) => at === index ? value : item))} />)}
      <HowFar issue={issue} save={save} />
      <div className="politics-actions">
        <button type="submit" className="button primary">Save</button>
        <button type="button" className="button quiet" onClick={close}>Cancel</button>
        <button type="button" className="button quiet" onClick={() => setConfirming(true)}>Put this issue away</button>
      </div>
      {confirming && <PutAway title={`Put ${issue.title} away?`} close={() => setConfirming(false)} away={() => save(`/issues/${encodeURIComponent(issue.id)}`, undefined, 'DELETE')}>
        <p>People stop talking about it, and it won't come back.</p>
      </PutAway>}
    </form>
  )
}

/** How far a local issue has got and how it went; a big question of the era is left to its times. */
function HowFar({ issue, save }: { issue: PoliticsIssue; save: Save }) {
  if (issue.kind !== 'local') return <p className="subtle">{issue.real ? 'History sets' : 'The times set'} how hot this gets.</p>
  const patch = (body: object) => void save(`/issues/${encodeURIComponent(issue.id)}`, body, 'PATCH')
  const outcome = issue.settled?.picked_by === 'user' ? String(issue.settled.picked) : ''
  const stage = issue.stage_by === 'you' ? issue.stage : 'game'
  return (<>
    {!issue.settled && <Choice id={`stage-${issue.id}`} label="How far it has got" value={stage}
      options={[{ value: 'game', label: `Let the game decide (${stageLabel({ stage: issue.stage, real: false }).toLowerCase()})` }, ...STAGE_CHOICES]}
      onChange={(value) => patch({ stage: value === 'game' ? null : value })} />}
    <Choice id={`outcome-${issue.id}`} label="How it went" value={outcome} options={outcomeChoices(issue)}
      onChange={(value) => patch({ outcome: value === '' ? null : Number(value) })} />
  </>)
}

function PutAway({ title, children, close, away }: { title: string; children: ReactNode; close: () => void; away: () => Promise<boolean> }) {
  return (
    <ConfirmDialog title={title} onClose={close} actions={<>
      <button type="button" className="button" onClick={close}>Keep it</button>
      <button type="button" className="button danger" onClick={() => void away().then(close)}>Put it away</button>
    </>}>{children}</ConfirmDialog>
  )
}

function Text({ id, label, value, onChange, required = true, max = 80 }: { id: string; label: string; value: string; onChange: (value: string) => void; required?: boolean; max?: number }) {
  return (
    <div className="politics-field">
      <label htmlFor={id}>{label}</label>
      <input id={id} value={value} required={required} maxLength={max} autoComplete="off" onChange={(event) => onChange(event.target.value)} />
    </div>
  )
}

function Choice({ id, label, value, options, onChange }: { id: string; label: string; value: string; options: { value: string; label: string }[]; onChange: (value: string) => void }) {
  return (
    <div className="politics-field">
      <label htmlFor={id}>{label}</label>
      <select id={id} value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
      </select>
    </div>
  )
}

/** Something the player wants the town to argue about: it stays open until they say how it went. */
function AddIssue({ save }: { save: Save }) {
  const [adding, setAdding] = useState(false)
  if (!adding) return <p><button type="button" className="text-button" onClick={() => setAdding(true)}><Plus aria-hidden="true" />Add an issue</button></p>
  return <AddIssueForm save={save} close={() => setAdding(false)} />
}

function AddIssueForm({ save, close }: { save: Save; close: () => void }) {
  const box = useOpened<HTMLFormElement>()
  const [title, setTitle] = useState('')
  const [sides, setSides] = useState(['', ''])
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (await save('/issues', { title: title.trim(), sides: sides.map((side) => side.trim()) })) close()
  }
  return (
    <form ref={box} className="politics-form" onSubmit={(event) => void submit(event)} aria-label="Add an issue">
      <p className="subtle">People take sides by their work and character, the same as for the town's own issues.</p>
      <Text id="politics-new-title" label="What it's about" value={title} onChange={setTitle} />
      <Text id="politics-new-first" label="One side" value={sides[0]} onChange={(value) => setSides([value, sides[1]])} />
      <Text id="politics-new-second" label="The other side" value={sides[1]} onChange={(value) => setSides([sides[0], value])} />
      <div className="politics-actions">
        <button type="submit" className="button primary">Add the issue</button>
        <button type="button" className="button quiet" onClick={close}>Cancel</button>
      </div>
    </form>
  )
}

/** The factions, strongest first past five, with the rest one tap away. */
function Factions({ data, gm, save }: { data: TownPolitics; gm: boolean; save: Save }) {
  const [all, setAll] = useState(false)
  const sorted = data.factions.length > FACTIONS_SHOWN ? [...data.factions].sort((a, b) => b.pull - a.pull) : data.factions
  const shown = all ? sorted : sorted.slice(0, FACTIONS_SHOWN)
  return (<>
    <h3 className="politics-subhead">Factions</h3>
    {data.factions.length > 0
      ? <ul className="politics-list">{shown.map((faction) => <FactionItem key={faction.id} faction={faction} data={data} gm={gm} save={save} />)}</ul>
      : <p className="subtle">No factions in {data.city.name}.</p>}
    {sorted.length > shown.length && <p className="politics-more"><button type="button" className="text-button" onClick={() => setAll(true)}>Show {sorted.length - shown.length} more</button></p>}
    {gm && <AddFaction save={save} />}
  </>)
}

function FactionItem({ faction, data, gm, save }: { faction: PoliticsFaction; data: TownPolitics; gm: boolean; save: Save }) {
  const [open, setOpen] = useState(false)
  const names = new Map(data.people.map((person) => [person.key, person.name]))
  const members = faction.members.map((key) => names.get(key)).filter(Boolean)
  return (
    <li className="politics-faction">
      <strong>{faction.name}</strong> <span className="subtle">{faction.kind.charAt(0).toUpperCase()}{faction.kind.slice(1)}{faction.power ? ', one of the powers here' : ''}. {pullText(faction)}.{members.length ? ` ${members.join(', ')} ${members.length === 1 ? 'belongs' : 'belong'}.` : ''}</span>
      <button type="button" className="text-button" aria-expanded={open} onClick={() => setOpen((value) => !value)}>{open ? 'Less' : 'More'}</button>
      {open && <FactionDetail faction={faction} data={data} gm={gm} save={save} />}
    </li>
  )
}

function FactionDetail({ faction, data, gm, save }: { faction: PoliticsFaction; data: TownPolitics; gm: boolean; save: Save }) {
  const allies = alliesText(faction.id, data)
  const [editing, setEditing] = useState(false)
  return (
    <div className="politics-detail">
      {faction.about && <p>{faction.about}</p>}
      {allies && <p className="subtle">{allies}</p>}
      {gm && (editing
        ? <FactionForm faction={faction} data={data} save={save} close={() => setEditing(false)} />
        : <p><button type="button" className="text-button" onClick={() => setEditing(true)}>Change this faction</button></p>)}
    </div>
  )
}

/** Name and pull, where it stands on each issue, how it gets on with every other faction, or put it away. A world
 *  power changed here changes in this town's talk only. */
function FactionForm({ faction, data, save, close }: { faction: PoliticsFaction; data: TownPolitics; save: Save; close: () => void }) {
  const box = useOpened<HTMLDivElement>()
  const [name, setName] = useState(faction.name)
  const [confirming, setConfirming] = useState(false)
  const path = `/factions/${encodeURIComponent(faction.id)}`
  const patch = (body: object) => void save(path, body, 'PATCH')
  const names = new Map(data.factions.map((item) => [item.id, item.name]))
  const links = relationsOf(faction.id, data.relations).filter((link) => names.has(link.other))
  return (
    <div ref={box} className="politics-form">
      <form className="politics-actions" onSubmit={(event) => { event.preventDefault(); patch({ name: name.trim() }) }} aria-label={`Rename ${faction.name}`}>
        <label className="visually-hidden" htmlFor={`faction-name-${faction.id}`}>Name</label>
        <input id={`faction-name-${faction.id}`} value={name} required maxLength={80} autoComplete="off" onChange={(event) => setName(event.target.value)} />
        <button type="submit" className="button">Rename</button>
      </form>
      <Choice id={`pull-${faction.id}`} label="Pull" value={String(faction.pull)} options={[1, 2, 3, 4, 5].map((pull) => ({ value: String(pull), label: pullText({ pull, change: 0 }) }))} onChange={(value) => patch({ pull: Number(value) })} />
      {data.issues.length > 0 && <h4 className="politics-subhead">Where it stands</h4>}
      {data.issues.map((issue) => (
        <Choice key={issue.id} id={`line-${faction.id}-${issue.id}`} label={issue.title} value={issue.id in faction.sides ? String(faction.sides[issue.id]) : 'game'}
          options={[{ value: 'game', label: `Let the game decide (${lineText(issue, issue.lines[faction.id])})` }, ...issue.sides.map((side, index) => ({ value: String(index), label: `Backs ${side.name}` }))]}
          onChange={(value) => patch({ issue: issue.id, side: value === 'game' ? null : Number(value) })} />
      ))}
      {links.length > 0 && <details className="politics-gets-on">
        <summary className="politics-subhead">How it gets on with the others ({links.length})</summary>
        {links.map((link) => (
          <Choice key={link.other} id={`with-${faction.id}-${link.other}`} label={names.get(link.other)!} value={String(link.stance)}
            options={STANCES.map((stance) => ({ value: String(stance.value), label: stance.label }))}
            onChange={(value) => void save('/relations', { a: faction.id, b: link.other, stance: Number(value) }, 'PUT')} />
        ))}
      </details>}
      <div className="politics-actions">
        <button type="button" className="button quiet" onClick={close}>Done</button>
        <button type="button" className="button quiet" onClick={() => setConfirming(true)}>Put this faction away</button>
      </div>
      {confirming && <PutAway title={`Put ${faction.name} away?`} close={() => setConfirming(false)} away={() => save(path, undefined, 'DELETE')}>
        <p>It drops out of {data.city.name}'s talk and won't come back: nobody belongs to it, and it backs no side.{faction.power ? ' It stays one of the world\'s powers.' : ''}</p>
      </PutAway>}
    </div>
  )
}

function lineText(issue: PoliticsIssue, line: number | null | undefined): string {
  return line === null || line === undefined ? 'stays out' : `backs ${issue.sides[line].name}`
}

function AddFaction({ save }: { save: Save }) {
  const [adding, setAdding] = useState(false)
  if (!adding) return <p><button type="button" className="text-button" onClick={() => setAdding(true)}><Plus aria-hidden="true" />Add a faction</button></p>
  return <AddFactionForm save={save} close={() => setAdding(false)} />
}

function AddFactionForm({ save, close }: { save: Save; close: () => void }) {
  const box = useOpened<HTMLFormElement>()
  const [name, setName] = useState('')
  const [kind, setKind] = useState('')
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (await save('/factions', { name: name.trim(), kind: kind.trim() })) close()
  }
  return (
    <form ref={box} className="politics-form" onSubmit={(event) => void submit(event)} aria-label="Add a faction">
      <Text id="faction-new-name" label="Name" value={name} onChange={setName} />
      <div className="politics-field">
        <label htmlFor="faction-new-kind">What kind</label>
        <input id="faction-new-kind" value={kind} maxLength={40} autoComplete="off" placeholder="a guild, a party, a gang" onChange={(event) => setKind(event.target.value)} />
      </div>
      <div className="politics-actions">
        <button type="submit" className="button primary">Add the faction</button>
        <button type="button" className="button quiet" onClick={close}>Cancel</button>
      </div>
    </form>
  )
}
