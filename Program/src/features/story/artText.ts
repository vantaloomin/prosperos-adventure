// Art on request (dungeon/art.py): what each picture is of, and where it stands.
import type { StoryArt, StoryPerson } from '../../types'

/** "You", "Fenwick Cutter", "Pell Provisions", "A passage". */
export function artLabel(item: Pick<StoryArt, 'kind' | 'subject'>, people: Pick<StoryPerson, 'key' | 'name'>[], placeName = ''): string {
  if (item.kind === 'portrait') return item.subject === 'player' ? 'You' : people.find((person) => person.key === item.subject)?.name ?? 'Someone you met'
  if (item.kind === 'passage') return 'A passage'
  const place = placeName || placeWords(item.subject)
  return item.kind === 'scene' ? `The scene at ${place}` : place[0].toUpperCase() + place.slice(1)
}

/** "kingswood/pell-provisions" as "pell provisions". */
const placeWords = (subject: string) => subject.split('/').pop()?.replace(/-/g, ' ') || 'the place'

/** Where a picture stands, in words; '' when it is made and current. */
export function artStatus(item: Pick<StoryArt, 'status' | 'error' | 'stale'>): string {
  if (item.status === 'queued' || item.status === 'running') return 'Making it…'
  if (item.status === 'refused' || item.status === 'failed') return item.error || 'It could not be made.'
  return item.stale ? 'Out of date: something has changed since.' : ''
}

/** Whether the gallery should look again soon: a picture is still being made. */
export const making = (items: Pick<StoryArt, 'status'>[]) => items.some((item) => item.status === 'queued' || item.status === 'running')

/** Who a portrait can be asked of: the people here first ("the barkeep", or their name once met), then everyone
 *  else met, each once. */
export function pictureChoices(people: Pick<StoryPerson, 'key' | 'name'>[], present: { key: string; label: string }[]): { key: string; label: string }[] {
  const here = new Set(present.map((item) => item.key))
  return [...present.map((item) => ({ key: item.key, label: `${item.label} (here)` })),
    ...people.filter((person) => !here.has(person.key)).map((person) => ({ key: person.key, label: person.name }))]
}
