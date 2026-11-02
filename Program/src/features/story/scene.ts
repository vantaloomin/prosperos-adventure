import type { Story, StoryPerson } from '../../types'

/** What the side of the play screen can show (requirements "Play screen and widgets"): the scene panel picks one or
 *  two of them from the game state, and the drawer holds every one. `here` is the people met who are where the story
 *  is; `pack` is the purse, the pack and, in a shop, its counter. */
export type Widget = 'fight' | 'here' | 'sheet' | 'pack' | 'journal' | 'map' | 'town' | 'people' | 'party' | 'powers' | 'chapters' | 'branches' | 'notebook' | 'dice' | 'export' | 'rules' | 'art' | 'inside' | 'talk'

export const WIDGET_NAMES: Record<Widget, string> = {
  fight: 'The fight', here: 'Here with you', sheet: 'Sheet', pack: 'Pack', journal: 'Journal', map: 'Map', town: 'Town', people: 'People', party: 'Party',
  powers: 'Powers', chapters: 'Chapters', branches: 'Branches', notebook: 'Notebook', dice: 'Dice log', export: 'Export', rules: 'Tone and rules', art: 'Pictures', inside: 'Inside', talk: 'Talk of the town',
}

/** The drawer's own tabs; the rest wait under More. */
export const TABS: Widget[] = ['sheet', 'pack', 'journal']
export const MORE: Widget[] = ['inside', 'map', 'town', 'talk', 'people', 'party', 'art', 'powers', 'chapters', 'branches', 'notebook', 'dice', 'export', 'rules']
/** The scene panel shows at most this many of its own picks, so the story keeps the room. */
const MOST = 2

/** Places on the Road (world/data/cities/<world>-road.json) are the towns not yet built out, reached on foot. */
export function onTheRoad(story: Story): boolean {
  return story.scene.city.id.endsWith('-road')
}

export function peopleHere(story: Story): StoryPerson[] {
  const { city, place } = story.scene
  return story.people.filter((person) => person.party || (person.place?.id === place.id && person.place.city_id === city.id))
}

/** Who travels with the character (dungeon/party.py). */
export function partyOf(story: Story): StoryPerson[] {
  return story.people.filter((person) => person.party)
}

/** The scene panel's widgets, chosen by code from the game state with no model call: a fight shows the fight, a shop
 *  its counter, an interior its rooms map, the road the map, and company the people here. With none of those it shows the journal. `shop` is
 *  whether the pack has a shop window where the story is (dungeon/inventory.py). */
export function sceneWidgets(story: Story, shop: boolean): Widget[] {
  const picked: Widget[] = []
  if (story.fight.fight) picked.push('fight')
  if (story.interior) picked.push('inside')
  if (shop) picked.push('pack')
  if (onTheRoad(story) && story.map) picked.push('map')
  if (peopleHere(story).length) picked.push('here')
  return picked.length ? picked.slice(0, MOST) : ['journal']
}

/** Whether a widget has anything to show in this story (the drawer leaves out the empty ones). */
export function hasWidget(story: Story, widget: Widget): boolean {
  const started = story.messages.length > 0
  const shown: Record<Widget, boolean> = {
    fight: !!story.fight.fight, here: peopleHere(story).length > 0, sheet: started, pack: started, journal: started,
    map: started && !!story.map, town: started && !onTheRoad(story), people: story.people.length > 0, party: partyOf(story).length > 0, powers: !!story.factions?.length || !!story.tier,
    chapters: !!story.campaign?.chapters.length, branches: !story.campaign?.ironman && story.branches.some((branch) => !branch.playing),
    notebook: started, dice: started && story.dice_shown, export: started, rules: true, art: started, inside: !!story.interior,
    talk: started && !!story.politics,
  }
  return shown[widget]
}

/** A widget asked for from elsewhere (a Settings search lands on Tone and rules), kept until the panel takes it. */
let asked: Widget | null = null
export const ASK_EVENT = 'story-drawer'

export function askForDrawer(widget: Widget) {
  asked = widget
  window.dispatchEvent(new Event(ASK_EVENT))
}

export function takeAsked(): Widget | null {
  const widget = asked
  asked = null
  return widget
}

/** The widgets the player pinned to the scene panel: a convenience of this browser, so it is kept here. */
const PINS = 'dungeon.story.pins'

export function loadPins(): Widget[] {
  try {
    const saved: unknown = JSON.parse(localStorage.getItem(PINS) ?? '[]')
    return Array.isArray(saved) ? saved.filter((item): item is Widget => typeof item === 'string' && item in WIDGET_NAMES) : []
  } catch { return [] }
}

export function savePins(pins: Widget[]) {
  try { localStorage.setItem(PINS, JSON.stringify(pins)) } catch { /* kept for this visit only */ }
}
