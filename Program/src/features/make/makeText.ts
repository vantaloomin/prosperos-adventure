/** Making your own character on the cast page (adventure/making.py): the form's state, what it sends, and the words it
 * shows. From Prospero's Companion's quick start, paste box and character form, cut to what the cast page needs. */
import type { PersonaGender } from '../../types'
import type { PartyMind } from '../round/round'

export type PersonalityKey = 'social' | 'warmth' | 'order' | 'curiosity' | 'stress'
export interface PersonalitySlider { level: 0 | 1 | 2; source: 'rolled' | 'idea' | 'you' }
export type PersonalitySliders = Partial<Record<PersonalityKey, PersonalitySlider>>
export interface PersonalityTrait { key: PersonalityKey; name: string; low: string; high: string }
export interface PersonalityView { sliders: PersonalitySliders; chips: string[]; traits: PersonalityTrait[] }

export const NUMBER_LOOKS = ['height_cm', 'weight_kg'] as const
export const WORD_LOOKS = ['build', 'skin', 'face', 'jaw', 'nose', 'eyes', 'eye_shape', 'hair', 'facial_hair', 'feature'] as const
export type WordLook = typeof WORD_LOOKS[number]
export type Looks = Partial<Record<WordLook, string> & Record<typeof NUMBER_LOOKS[number], number | null>>
export interface LooksView { automatic: Looks & { age?: number | null }; options: Partial<Record<WordLook, string[]>> }
export interface PerceptionView { automatic: { seen_as: string; sees_self: string }; seen_as: string[]; sees_self: string[] }

/** The fields the model drafts and splits into. */
export const DRAFTED = ['name', 'gender', 'age', 'about', 'look', 'voice', 'wants', 'fears'] as const
export interface Drafted { name: string; gender: PersonaGender; age: number | null; about: string; look: string; voice: string; wants: string; fears: string }

/** A character card opened into the paste box (/story/make/card), and what the person ticked to keep from it at
 * Begin: its lorebook, and its picture as the portrait. `data` is the file, sent again at Begin. */
export interface OpenedCard {
  filename: string; data: string; name: string; book: { name: string; entries: number } | null; picture: string | null
  lorebook: boolean; usePicture: boolean
}

/** The whole form: who they are, how they look and talk, the extras rolled from `seed` until set, and a card opened. */
export interface MadeForm {
  seed: string; name: string; gender: PersonaGender; age: string; about: string; look: string; voice: string; wants: string; fears: string
  personality_sliders: PersonalitySliders | null; looks: Looks; seen_as: string; sees_self: string; card: OpenedCard | null
}

export function emptyForm(seed: string): MadeForm {
  return { seed, name: '', gender: '', age: '', about: '', look: '', voice: '', wants: '', fears: '', personality_sliders: null, looks: {}, seen_as: '', sees_self: '', card: null }
}

/** A seed for a new form, so every new character rolls its own sliders, Looks and lines. */
export function newSeed(random: () => number = Math.random): string {
  return Array.from({ length: 12 }, () => Math.floor(random() * 36).toString(36)).join('')
}

/** A draft or a split, laid over the form: every field it gives replaces the form's; the extras stay. */
export function withDraft(form: MadeForm, draft: Drafted): MadeForm {
  return { ...form, name: draft.name || form.name, gender: draft.gender || form.gender, age: draft.age ? String(draft.age) : form.age,
    about: draft.about, look: draft.look, voice: draft.voice, wants: draft.wants, fears: draft.fears }
}

/** The quick start's picks: whatever the form already says, and the idea. */
export function picksOf(form: MadeForm, idea: string, party = false) {
  return { name: form.name.trim(), gender: form.gender, ...(form.age ? { age: Number(form.age) } : {}), idea: idea.trim(), ...(party ? { party } : {}) }
}

/** Looks the person set, without the empty ones. */
export function setLooks(looks: Looks): Looks {
  return Object.fromEntries(Object.entries(looks).filter(([, value]) => value !== '' && value !== null && value !== undefined)) as Looks
}

/** The form as the sheet's rolls read it (sliders, Looks, perception), for /story/make/*: never the card. */
export function sheetBody(form: MadeForm) {
  return { ...sheetFields(form), name: form.name.trim(), gender: form.gender, about: form.about.trim(), ...(form.age ? { age: Number(form.age) } : {}) }
}

/** What Begin sends besides the persona (adventure/models.py MadeCharacter), with the card when something is ticked. */
export function madeBody(form: MadeForm) {
  return { ...sheetFields(form), ...cardBody(form.card) }
}

/** The card's part of Begin: the file and what to keep from it, or nothing when nothing it holds is ticked. */
export function cardBody(card: OpenedCard | null) {
  const lorebook = !!(card?.lorebook && card.book)
  const picture = !!(card?.usePicture && card.picture)
  return card && (lorebook || picture) ? { card: { filename: card.filename, data: card.data, lorebook, picture } } : {}
}

function sheetFields(form: MadeForm) {
  return { seed: form.seed, look: form.look.trim(), voice: form.voice.trim(), wants: form.wants.trim(), fears: form.fears.trim(),
    ...(form.personality_sliders ? { personality_sliders: form.personality_sliders } : {}), looks: setLooks(form.looks),
    seen_as: form.seen_as.trim(), sees_self: form.sees_self.trim() }
}

/** A party member the player makes on the cast page (adventure/rounds/cast.py `join_made`): their form, and whether
 * they think for themselves or run on the rules. `key` is the page's own, for the card and the form under the grid. */
export interface MadeMember { key: string; form: MadeForm; mind: PartyMind }

export function newMember(key: string): MadeMember {
  return { key, form: emptyForm(newSeed()), mind: 'agent' }
}

/** Ready for Begin: a name, and an adult age or none. */
export function memberReady(member: MadeMember): boolean {
  const years = member.form.age ? Number(member.form.age) : null
  return !!member.form.name.trim() && (years === null || (Number.isInteger(years) && years >= 18 && years <= 120))
}

/** One of Begin's `made_party`: who they are, the sheet's extras, and how they decide. */
export function memberBody({ form, mind }: MadeMember) {
  return { name: form.name.trim(), gender: form.gender, ...(form.age ? { age: Number(form.age) } : {}), about: form.about.trim(), ...madeBody(form), mind }
}

/** The fields a split filled in because the pasted text said nothing about them, by their labels. */
export function filledLine(keys: string[]): string {
  const named = keys.map((key) => FIELD_NAMES[key as keyof typeof FIELD_NAMES]).filter(Boolean)
  return named.length ? `${MAKE_TEXT.filledIn}: ${named.join(', ')}` : ''
}

/** A slider's stop in words: an end's words, or "In between". */
export function levelLabel(trait: PersonalityTrait, level: number): string {
  return level === 0 ? trait.low : level === 2 ? trait.high : MAKE_TEXT.between
}

/** Who set a slider. */
export function sourceLabel(source: PersonalitySlider['source']): string {
  return source === 'you' ? MAKE_TEXT.setByYou : source === 'idea' ? MAKE_TEXT.fromWords : MAKE_TEXT.rolled
}

/** The person moved a slider: it is theirs now. */
export function moved(sliders: PersonalitySliders, key: PersonalityKey, level: number): PersonalitySliders {
  return { ...sliders, [key]: { level: Math.max(0, Math.min(2, Math.round(level))) as 0 | 1 | 2, source: 'you' } }
}

/** Handing a slider back: it is left out, and the app settles it again from the words and the seed. */
export function released(sliders: PersonalitySliders, key: PersonalityKey): PersonalitySliders {
  const next = { ...sliders }
  delete next[key]
  return next
}

/** Whether two slider sets say the same, so the form only takes the app's answer when it changes something. */
export function sameSliders(a: PersonalitySliders | null | undefined, b: PersonalitySliders | null | undefined): boolean {
  const keys: PersonalityKey[] = ['social', 'warmth', 'order', 'curiosity', 'stress']
  return keys.every((key) => a?.[key]?.level === b?.[key]?.level && a?.[key]?.source === b?.[key]?.source)
}

/** 5'7" (170 cm): both units. */
export function heightLabel(cm: number): string {
  const inches = Math.round(cm / 2.54)
  return `${Math.floor(inches / 12)}'${inches % 12}" (${cm} cm)`
}

export function weightLabel(kg: number): string {
  return `${Math.round(kg * 2.20462)} lb (${kg} kg)`
}

/** Heights by the inch from 4'6" to 7'2", weights every 5 lb from 80 to 400, inside what the server takes. */
export function numberChoices(kind: 'height_cm' | 'weight_kg'): number[] {
  if (kind === 'height_cm') return Array.from({ length: 33 }, (_, index) => Math.round((54 + index) * 2.54))
  return Array.from({ length: 65 }, (_, index) => Math.round((80 + index * 5) / 2.20462))
}

/** A Looks field's empty choice: what the app draws, or that the look already says it. */
export function drawnLabel(value: string | number | null | undefined, format: (value: number) => string = String): string {
  if (value === null || value === undefined || value === '') return MAKE_TEXT.inLook
  return typeof value === 'number' ? format(value) : value
}

const FIELD_NAMES = { name: 'Name', gender: 'Gender', age: 'Age', about: 'About you', look: 'Look', voice: 'Voice', wants: 'Wants', fears: 'Fears' }

export const LOOKS_LABELS: Record<typeof NUMBER_LOOKS[number] | WordLook, string> = {
  height_cm: 'Height', weight_kg: 'Weight', build: 'Build', skin: 'Skin', face: 'Face shape', jaw: 'Jaw and chin', nose: 'Nose',
  eyes: 'Eye color', eye_shape: 'Eye shape', hair: 'Hair', facial_hair: 'Facial hair', feature: 'Something people notice',
}

export const MAKE_TEXT = {
  idea: 'Idea',
  ideaPlaceholder: 'A barge pilot who owes the lock-keepers',
  write: 'Write it',
  writing: 'Writing…',
  addModel: 'Add a model',
  paste: 'Paste a character',
  pasted: 'Character',
  open: 'Open a card',
  split: 'Fill in the fields',
  splitting: 'Filling in…',
  filledIn: 'Written for you',
  look: 'Look',
  voice: 'Voice',
  wants: 'Wants',
  fears: 'Fears',
  personality: 'Personality',
  roll: 'Roll again',
  between: 'In between',
  rolled: 'Rolled',
  fromWords: 'From your words',
  setByYou: 'Set by you',
  handBack: (trait: string) => `Roll ${trait.toLowerCase()} again`,
  looks: 'Looks',
  inLook: 'As your look says',
  you: { seen: 'How you come across', seenAs: 'How others see you', seesSelf: 'How you see yourself', pickSeenAs: 'Pick how others see you', pickSeesSelf: 'Pick how you see yourself' },
  them: { seen: 'How they come across', seenAs: 'How others see them', seesSelf: 'How they see themself', pickSeenAs: 'Pick how others see them', pickSeesSelf: 'Pick how they see themself' },
  about: 'About them',
  aboutYou: 'About you',
  member: 'Make a party member',
  unnamed: 'New party member',
  removeMember: (name: string) => `Remove ${name} from your party`,
  failed: 'That did not work. Try again.',
  cardOf: (name: string) => name ? `${name}'s card` : 'The card',
  usePicture: 'Use its picture',
  addBook: (name: string, entries: number) => `Add its lorebook, ${name} (${entries} ${entries === 1 ? 'entry' : 'entries'})`,
}
