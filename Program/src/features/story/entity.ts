import type { Gear, JournalEntry, Story } from '../../types'
import { gearLine, personLine } from './storyText.ts'

/** Something in the story the player can look at more closely (requirements "Play screen and widgets", rule 2: one
 *  entity card). A name in the prose, a person met, a place on the map, an item in the pack and a faction all open
 *  the same card. */
export type EntityRef = { kind: 'person'; key: string } | { kind: 'place'; id: string } | { kind: 'item'; id: string } | { kind: 'faction'; id: string }

/** What a card's button does: write `line` into the composer for the turn loop to roll and apply (rule 1: widgets
 *  propose, the story decides), or, for `find`, move the story to where that person is now (an out-of-story jump). */
export interface CardAction { label: string; line?: string; find?: string }

/** A card: what the thing is, what the character has seen of it, what they know (facts the game keeps, never hidden
 *  truth: rule 4), and what they can do. */
export interface Card { title: string; kind: string; about: string[]; known: string[]; actions: CardAction[]; picture?: string | null }

const lower = (text: string) => text.charAt(0).toLowerCase() + text.slice(1)
const first = (name: string) => name.split(' ')[0]

/** The facts the character knows about something, by what they are about. The GM view's journal holds hidden truth
 *  too; a card leaves it out. */
export function knownAbout(entries: JournalEntry[], names: string[]): string[] {
  const wanted = names.map((name) => name.toLowerCase())
  return entries.filter((entry) => entry.truth !== 'world' && wanted.includes(entry.subject.toLowerCase())).map((entry) => entry.text)
}

function personCard(story: Story, key: string, entries: JournalEntry[]): Card | null {
  const person = story.people.find((one) => one.key === key)
  if (!person) return null
  const here = person.place?.id === story.scene.place.id && person.place.city_id === story.scene.city.id
  const actions: CardAction[] = here ? [{ label: `Talk to ${first(person.name)}`, line: `I turn to ${person.name}.` }]
    : person.place ? [{ label: `Go to ${first(person.name)}`, find: person.key }] : []
  actions.push({ label: 'Ask around about them', line: `I ask around about ${person.name}.` })
  return {
    title: person.name, kind: `${person.role}, ${person.city}`, about: [personLine(person), person.feelings].filter(Boolean),
    known: [...person.notes, ...knownAbout(entries, [person.name])], actions,
  }
}

const DANGER = { none: 'safe', low: 'little danger', medium: 'some danger', high: 'dangerous' }

function placeCard(story: Story, id: string, entries: JournalEntry[]): Card | null {
  const place = story.map?.places.find((one) => one.id === id)
  if (!place || !story.map) return null
  const names = new Map(story.map.places.map((one) => [one.id, one.name]))
  const roads = story.map.roads.filter((road) => road.from === id || road.to === id).map((road) =>
    `To ${names.get(road.from === id ? road.to : road.from)}: ${road.hours} hours on foot, ${road.terrain}, ${DANGER[road.danger]}`)
  return {
    title: place.name, kind: place.here ? 'You are here' : place.visited ? 'You have been there' : 'You have heard of it',
    about: roads, known: knownAbout(entries, [place.name]),
    actions: place.here ? [] : [{ label: 'Set out for it', line: `I set out for ${place.name}.` }],
  }
}

function itemCard(gear: Gear | undefined, id: string, entries: JournalEntry[]): Card | null {
  const item = gear?.items.find((one) => one.id === id)
  if (!item) return null
  const name = lower(item.name)
  const actions: CardAction[] = [{ label: 'Use it', line: `I use my ${name}.` }, { label: 'Look it over', line: `I look over my ${name}.` }]
  if (gear?.shop?.open && gear.shop.offers[id] !== undefined) actions.push({ label: 'Offer it to sell', line: `I offer to sell my ${name}.` })
  return { title: item.name, kind: item.category, about: [`In your pack: ${gearLine(item)}`], known: knownAbout(entries, [item.name]), actions, picture: item.icon }
}

function factionCard(story: Story, id: string, entries: JournalEntry[]): Card | null {
  const faction = story.factions?.find((one) => one.id === id)
  if (!faction) return null
  return {
    title: faction.name, kind: 'A power in the world', about: [faction.summary, `You are ${faction.standing} to them.`],
    known: knownAbout(entries, [faction.name]), actions: [{ label: 'Ask around about them', line: `I ask around about ${faction.name}.` }],
    picture: faction.emblem,
  }
}

/** The card for something, from what the screen already holds: the story, the pack and the journal. Null when it is
 *  gone (an item sold since, say). */
export function cardOf(entity: EntityRef, story: Story, gear: Gear | undefined, entries: JournalEntry[]): Card | null {
  if (entity.kind === 'person') return personCard(story, entity.key, entries)
  if (entity.kind === 'place') return placeCard(story, entity.id, entries)
  if (entity.kind === 'item') return itemCard(gear, entity.id, entries)
  return factionCard(story, entity.id, entries)
}

export interface NameLink { name: string; entity: EntityRef }

/** Words that start a name but say nothing on their own ("the barkeep" is not a first name). */
const NOT_NAMES = new Set(['the', 'a', 'an', 'old', 'young', 'master', 'mistress', 'sir', 'lady', 'lord'])

/** The names the prose can link: people met (their whole name, and their first name when no one else shares it)
 *  and the factions known. Longest first, so "Agnes Brill" wins over "Agnes". */
export function namesIn(story: Story): NameLink[] {
  const links: NameLink[] = story.people.map((person) => ({ name: person.name, entity: { kind: 'person', key: person.key } }))
  const firsts = story.people.map((person) => first(person.name))
  story.people.forEach((person, index) => {
    const name = firsts[index]
    const alone = firsts.filter((one) => one === name).length === 1
    if (name !== person.name && alone && name.length > 2 && !NOT_NAMES.has(name.toLowerCase())) links.push({ name, entity: { kind: 'person', key: person.key } })
  })
  for (const faction of story.factions ?? []) links.push({ name: faction.name, entity: { kind: 'faction', id: faction.id } })
  return links.sort((one, other) => other.name.length - one.name.length)
}

const escaped = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

/** Text cut into plain runs and linked names, whole words only. */
export function linkText(text: string, links: NameLink[]): (string | NameLink)[] {
  if (!links.length) return [text]
  const byName = new Map(links.map((link) => [link.name, link]))
  const pattern = new RegExp(`(?<![\\p{L}\\p{N}])(${links.map((link) => escaped(link.name)).join('|')})(?![\\p{L}\\p{N}])`, 'gu')
  return text.split(pattern).map((part, index) => index % 2 === 1 ? byName.get(part)! : part).filter((part) => part !== '')
}
