import type { BandStep, DiceLog, DramaLevel, Gear, HiddenRoll, IntensityPreset, JournalEntry, JournalInstitution, JournalQuest, JournalThread, LegacyRole, Looks, NarrationLength, NarrationPov, NarrationTense, Premade, ReceiptChip, SheetBonds, SheetGrowth, Srd52Spells, StoryArc, StoryBranch, StoryChapter, StoryFight, StoryHand, StoryMessage, StoryPace, StoryPerson, StoryPlace, StoryRoll, StoryScene, StoryStart, StoryTier, ToneCategory, ToneVoice, TurnAction, TurnEvent, TurnPace, TurnSoFar, VeilTopic, Zone } from '../../types'

/** "Tuesday, 9:40 am" from the scene's local time, which is the city's own clock with no offset. */
export function sceneTime(localTime: string): string {
  const [day, clock] = localTime.split('T')
  const [year, month, date] = day.split('-').map(Number)
  const [hour, minute] = clock.split(':').map(Number)
  const weekday = new Date(Date.UTC(year, month - 1, date)).toLocaleDateString('en-US', { weekday: 'long', timeZone: 'UTC' })
  return `${weekday}, ${hour % 12 || 12}:${String(minute).padStart(2, '0')} ${hour < 12 ? 'am' : 'pm'}`
}

const COUNTS = ['', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten']

const IRREGULAR: Record<string, string> = { man: 'men', woman: 'women', person: 'people', child: 'children' }
// Words that end the role and start what follows it: "a head chef| at Joe's", "a neighbor| waiting for the bus".
const AFTER_ROLE = /^(.+?)((?: (?:from|at|of|in|on|with|near|by|for|who|that|behind|outside|inside|[a-z]+ing)\b|,).*)?$/

function plural(word: string): string {
  if (IRREGULAR[word]) return IRREGULAR[word]
  if (/(s|sh|ch|x|z)$/.test(word)) return `${word}es`
  return /[^aeiou]y$/.test(word) ? `${word.slice(0, -1)}ies` : `${word}s`
}

/** "head chef at Joe's" -> "head chefs at Joe's": the role's last word, its head noun, takes the plural. */
function pluralRole(phrase: string): string {
  const [, role, rest = ''] = AFTER_ROLE.exec(phrase) ?? [phrase, phrase, '']
  const words = role.split(' ')
  return [...words.slice(0, -1), plural(words[words.length - 1])].join(' ') + rest
}

/** Unnamed people who read the same are counted: three of "a local from Canton" are "three locals from Canton". */
export function grouped(around: string[]): string[] {
  const counts = new Map<string, number>()
  for (const who of around) counts.set(who, (counts.get(who) ?? 0) + 1)
  return [...counts.entries()].flatMap(([who, count]) => {
    const unnamed = /^(?:an?|the) (.+)$/.exec(who)
    if (count === 1) return [who]
    if (!unnamed) return Array<string>(count).fill(who)
    return [`${COUNTS[count] ?? count} ${pluralRole(unnamed[1])}`]
  })
}

/** "Nobody you would notice is here.", "The barista is here.", "A regular and two neighbors are here." */
export function aroundText(around: string[]): string {
  if (!around.length) return 'Nobody you would notice is here.'
  const names = grouped(around).map((who, index) => index ? who : who[0].toUpperCase() + who.slice(1))
  const list = names.length === 1 ? names[0] : `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`
  return `${list} ${around.length === 1 ? 'is' : 'are'} here.`
}

/** The city's places by neighborhood, for the place picker. */
export function placeGroups(places: StoryPlace[]): [string, StoryPlace[]][] {
  const groups = new Map<string, StoryPlace[]>()
  for (const place of places) groups.set(place.neighborhood, [...(groups.get(place.neighborhood) ?? []), place])
  return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b))
}

export function whereText(scene: StoryScene): string {
  return `${scene.place.name}, ${scene.place.neighborhood}, ${scene.city.name}`
}

/** "Inside: the back patio, the bar seats" */
export function spotsText(spots: string[]): string {
  return `Inside: ${spots.join(', ')}`
}

/** "Met once · now working as the barista at The Daily Grind" */
export function personLine(person: StoryPerson): string {
  const times = person.meetings === 1 ? 'once' : person.meetings === 2 ? 'twice' : `${person.meetings} times`
  const where = person.place && !person.doing.includes(person.place.name) ? ` at ${person.place.name}` : ''
  return `Met ${times} · now ${person.doing}${where}`
}

/** What a roll tested, as the card heads it: "Allure · hard", or under 5E "Athletics · DC 15". */
export function rollWhat(roll: StoryRoll): string {
  if (roll.ruleset === 'fate') return fateLine(roll.skill)
  if (roll.ruleset === 'ironsworn') return (roll.skill ?? '').replace(/ vs .*$/, '')
  if (roll.ruleset === 'brp') return roll.skill ?? roll.stat
  return roll.target ? `${roll.skill} · DC ${roll.target}` : `${roll.stat} · ${roll.difficulty.replace('_', ' ')}`
}

/** "Allure d8: 62 + 5, hard (-10) = 57, Success at a cost"; under 5E "Athletics d20: 12 + 5 = 17 vs DC 15, Success". */
/** A check that needed no dice: a 5E spell with no slot left just fails (dungeon/sheet.py cast). */
export function unrolled(roll: StoryRoll): boolean {
  return roll.ruleset === 'srd52' && roll.natural === 0
}

export function rollText(roll: StoryRoll): string {
  if (unrolled(roll)) return `${roll.skill}: no roll, ${roll.label}`
  if (roll.ruleset === 'fate') return `${fateLine(roll.skill)}: ${signed(roll.natural)} + ${roll.bonus} = ${fateLadder(roll.total)} (${signed(roll.total)}), ${roll.label}`
  return dicedText(roll)
}

/** A Fate roll's line without its dice ("Sneaky +3 vs Fair (+2) (stunt +2)"), and its four faces (dungeon/rules/fate.py). */
export function fateLine(skill: string | null | undefined): string {
  return (skill ?? '').replace(/, dice [+0−]{4}$/, '')
}

export function fateFaces(skill: string | null | undefined): string[] {
  const found = /, dice ([+0−]{4})$/.exec(skill ?? '')
  return found ? [...found[1]] : ['0', '0', '0', '0']
}

const FATE_LADDER = ['Terrible', 'Poor', 'Mediocre', 'Average', 'Fair', 'Good', 'Great', 'Superb', 'Fantastic', 'Epic', 'Legendary']

/** Where a total sits on the Fate ladder: -2 Terrible up to +8 Legendary. */
export function fateLadder(total: number): string {
  return FATE_LADDER[Math.max(0, Math.min(FATE_LADDER.length - 1, total + 2))]
}

function dicedText(roll: StoryRoll): string {
  if (roll.ruleset === 'ironsworn') return `${roll.skill}: ${roll.natural} + ${roll.bonus} = ${roll.total}, ${roll.label}`
  if (roll.ruleset === 'brp') return `${roll.skill} d100: ${roll.natural} against ${roll.target ?? 0}, ${roll.label}`
  if (roll.target) {
    const bonus = roll.bonus < 0 ? ` - ${-roll.bonus}` : ` + ${roll.bonus}`
    return `${roll.skill} d20: ${roll.natural}${bonus} = ${roll.total} vs DC ${roll.target}, ${roll.label}`
  }
  const die = roll.die ? ` d${roll.die}` : ''
  const sum = roll.die ? `${roll.natural} + ${roll.bonus}` : `${roll.natural}`
  const shift = roll.shift ? `, ${roll.difficulty.replace('_', ' ')} (${roll.shift > 0 ? '-' : '+'}${Math.abs(roll.shift)})` : ''
  return `${roll.stat}${die}: ${sum}${shift} = ${roll.total}, ${roll.label}`
}

/** "a woman, 41" under a premade's name. */
export function premadeLine(premade: Pick<Premade, 'gender' | 'age'>): string {
  const gender = premade.gender === 'nonbinary' ? 'nonbinary' : premade.gender ? `a ${premade.gender}` : ''
  return [gender, premade.age ? String(premade.age) : ''].filter(Boolean).join(', ')
}

/** A made character starts with every stat as even as the points allow. */
export function startingStats(start: Pick<StoryStart, 'stat_names' | 'points' | 'range'>): Record<string, number> {
  const even = Math.min(start.range[1], Math.max(start.range[0], Math.floor(start.points / start.stat_names.length)))
  return Object.fromEntries(start.stat_names.map((stat) => [stat, even]))
}

/** "3 points left of 60", or how far over the pool the stats are. */
export function pointsText(left: number, points: number): string {
  const count = Math.abs(left)
  return `${count} ${count === 1 ? 'point' : 'points'} ${left < 0 ? 'over' : 'left'} of ${points}`
}

/** The points still to spend; below zero when the stats cost more than the pool. */
export function pointsLeft(stats: Record<string, number>, points: number): number {
  return points - Object.values(stats).reduce((sum, value) => sum + value, 0)
}

/** "3 turns, last played Tue 21 Oct" for a branch the player is not in. */
export function branchLine(branch: Pick<StoryBranch, 'turns' | 'last_at'>): string {
  const turns = `${branch.turns} ${branch.turns === 1 ? 'turn' : 'turns'}`
  if (!branch.last_at) return turns
  const day = new Date(branch.last_at)
  return `${turns}, last played ${day.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' })}`
}

const KINDS: Record<string, string> = { death: 'Death', item: 'Item', wound: 'Wound', promise: 'Promise', location: 'Place', secret: 'Secret', relationship: 'Relationship', fact: 'Fact' }

/** "Wound · you", and whether the character only believes it. */
export function journalKind(entry: Pick<JournalEntry, 'kind' | 'subject' | 'truth' | 'faded'>): string {
  const truth = entry.truth === 'belief' ? ' (you believe)' : entry.truth === 'world' ? ' (hidden from you)' : ''
  return `${KINDS[entry.kind] ?? 'Fact'} · ${entry.subject}${truth}${entry.faded ? ' · fading' : ''}`
}

const QUEST_ENDS: Record<string, string> = { done: 'Done', failed: 'Failed', missed: 'Too late' }

/** A quest's state in the journal: the story time left while it is open, else how it ended. */
export function questState(quest: Pick<JournalQuest, 'status' | 'left' | 'kind'>): string {
  const kind = quest.kind === 'job' ? 'Job · ' : quest.kind === 'oath' ? 'Oath · ' : quest.kind === 'coursework' ? 'Coursework · ' : ''
  if (quest.status !== 'open') return kind + (QUEST_ENDS[quest.status] ?? 'Over')
  return kind + (quest.left ? `Underway · ${quest.left}` : 'Underway')
}

/** "3.40 cr.", from hundredths of the currency. */
export function moneyText(hundredths: number, currency: Gear['currency']): string {
  return `${(hundredths / 100).toFixed(2)} ${currency.symbol || currency.name || ''}`.trim()
}

/** "Rope, fifty feet × 2". */
export function gearLine(item: { name: string; qty: number; stolen?: boolean; condition?: string }): string {
  const tags = [item.stolen && 'stolen', item.condition && item.condition !== 'sound' && item.condition].filter(Boolean)
  return (item.qty > 1 ? `${item.name} × ${item.qty}` : item.name) + (tags.length ? ` (${tags.join(', ')})` : '')
}

/** How the character looks, in a line: "Grimy (blood); clothes torn; outer clothing off (the Felled Oak)". */
export function looksText(looks: Looks): string {
  const parts = [looks.cleanliness.charAt(0).toUpperCase() + looks.cleanliness.slice(1), `clothes ${looks.clothes}`,
    ...Object.entries(looks.dress).map(([layer, value]) => `${layer} clothing ${value}`)]
  if (looks.on_show.length) parts.push(`on show: ${looks.on_show.join(', ')}`)
  return parts.join('; ')
}

/** "6.35 of 13 slots". */
export function slotsText(slots: Gear['slots']): string {
  const round = (value: number) => Number.isInteger(value) ? String(value) : value.toFixed(2).replace(/0$/, '')
  return slots.max == null ? `${round(slots.used)} slots, no limit` : `${round(slots.used)} of ${round(slots.max)} slots`
}

export function foeNumbers(foe: NonNullable<StoryFight['fight']>['foes'][number]): string {
  if (foe.max_hp !== undefined) return `, ${foe.hp} of ${foe.max_hp} HP`
  return foe.wound === null ? '' : `, wound ${foe.wound} of 5`
}

/** How far off a foe is, when it is not at arm's length. */
export function zoneText(zone?: Zone | null): string {
  return zone === 'near' ? ' · nearby' : zone === 'far' ? ' · far off' : ''
}

/** The header's fight line: who the character is fighting, or that they are dead; '' otherwise. How the character is
 *  sits in the status strip (statusItems). */
export function foesText(fight: StoryFight): string {
  if (fight.dead) return 'Your character is dead. Go back to an earlier line to play on.'
  const foes = fight.fight?.foes.map((foe) => `${foe.name} (${foe.state}${foeNumbers(foe)})`).join(', ')
  return foes ? `Fighting: ${foes}.` : ''
}

export interface StatusItem { kind: 'time' | 'condition' | 'nerve' | 'lasting' | 'held' | 'coin'; text: string; tone: 'neutral' | 'loss' }

const capital = (text: string) => text.charAt(0).toUpperCase() + text.slice(1)

function conditionItem(fight: StoryFight): StatusItem {
  const points = fight.max_hp === undefined ? '' : `, ${fight.hp} of ${fight.max_hp} HP`
  return { kind: 'condition', tone: fight.condition === 'unhurt' ? 'neutral' : 'loss', text: `${capital(fight.condition)}${points}` }
}

/** The status strip (requirements "Play screen and widgets"): the time, how the character is, their nerve, lasting
 *  injuries, captivity and coin, at a glance. Numbers come only as the story gives them, which is with the dice shown. */
export function statusItems(scene: Pick<StoryScene, 'local_time' | 'weather'>, fight: StoryFight, coin: string | null): StatusItem[] {
  const time: StatusItem = { kind: 'time', tone: 'neutral', text: sceneTime(scene.local_time) + (scene.weather ? ` · ${scene.weather}` : '') }
  if (fight.dead) return [time, { kind: 'condition', tone: 'loss', text: 'Dead' }]
  const items: (StatusItem | false)[] = [time, conditionItem(fight),
    { kind: 'nerve', tone: fight.stress ? 'loss' : 'neutral', text: `Nerve: ${fight.stress || 'steady'}` },
    !!fight.injuries?.length && { kind: 'lasting', tone: 'loss', text: `Lasting: ${fight.injuries.join(', ')}` },
    !!fight.captors && { kind: 'held', tone: 'loss', text: `Held by ${fight.captors}` },
    coin !== null && { kind: 'coin', tone: 'neutral', text: coin }]
  return items.filter((item): item is StatusItem => !!item)
}

const PRESET_NAMES: Record<Exclude<IntensityPreset, 'world'>, string> = {
  restrained: 'Restrained: implied, little detail', mature: 'Mature: shown plainly', unflinching: 'Unflinching: explicit, in full',
}

/** The choices for how far the story goes, the world's own first: "The world's own (Unflinching)". */
export function intensityChoices(world: Exclude<IntensityPreset, 'world'>): [IntensityPreset, string][] {
  return [['world', `The world's own (${PRESET_NAMES[world].split(':')[0]})`],
    ...(Object.entries(PRESET_NAMES) as [IntensityPreset, string][])]
}

const DRAMA_NAMES: Record<Exclude<DramaLevel, 'world'>, string> = {
  quiet: 'Quiet: little happens unbidden', uneasy: 'Uneasy: now and then', eventful: 'Eventful: often',
  merciless: 'Merciless: often, and the worst of it',
}

/** The choices for how eventful the story is, the world's own first: "The world's own (Eventful)". */
export function dramaChoices(world: Exclude<DramaLevel, 'world'>): [DramaLevel, string][] {
  return [['world', `The world's own (${DRAMA_NAMES[world].split(':')[0]})`],
    ...(Object.entries(DRAMA_NAMES) as [DramaLevel, string][])]
}

export const TONE_CATEGORIES: [ToneCategory, string][] = [['violence', 'Violence and gore'], ['sex', 'Sex'], ['horror', 'Horror'],
  ['cruelty', 'Cruelty and abuse'], ['drugs', 'Drugs']]
export const LEVEL_NAMES = ['Off the page', 'Restrained', 'Mature', 'Unflinching']
export const VEIL_TOPICS: [VeilTopic, string][] = [['torture', 'Torture'], ['sexual-violence', 'Sexual violence'], ['child-harm', 'Harm to children'],
  ['self-harm', 'Self-harm'], ['mutilation', 'Mutilation'], ['execution', 'Executions'], ['slavery', 'Slavery'], ['sacrifice', 'Sacrifice'],
  ['addiction', 'Addiction'], ['disease', 'Disease']]
/** The narration format's choices (dungeon/narration/prompt.py Format). */
export const POVS: [NarrationPov, string][] = [['third', 'Close third person ("she draws her knife")'],
  ['second', 'Second person ("you draw your knife")'], ['first', 'First person ("I draw my knife")']]
export const TENSES: [NarrationTense, string][] = [['past', 'Past tense'], ['present', 'Present tense']]
export const LENGTHS: [NarrationLength, string][] = [['short', 'Short (about 200 words a turn)'],
  ['medium', 'Medium (about 400 words)'], ['long', 'Long (800 words or more)']]

export const VOICES: [ToneVoice, string][] = [['grim', 'Grim'], ['wry', 'Wry'], ['romantic', 'Romantic'], ['hopeful', 'Hopeful'],
  ['lyrical', 'Lyrical'], ['plain', 'Plain']]

/** The veils with one topic added or taken away, in the list's own order. */
export function toggledVeil(veils: VeilTopic[], topic: VeilTopic, on: boolean): VeilTopic[] {
  const chosen = new Set(veils)
  if (on) chosen.add(topic)
  else chosen.delete(topic)
  return VEIL_TOPICS.map(([id]) => id).filter((id) => chosen.has(id))
}

/** "15% off today" or "20% dearer today" after a haggle; '' without one. */
export function haggleText(percent: number): string {
  return percent < 0 ? `${-percent}% off today` : percent > 0 ? `${percent}% dearer today` : ''
}

const STEP_NAMES: Record<string, string> = { contradiction: 'the contradiction check', rewrite: 'the prose rewrite' }

/** "14 rolls, 9 landed (64%)": the dice log's tally. */
export function tallyText(tally: NonNullable<DiceLog['tally']>): string {
  if (!tally.rolls) return 'No rolls yet.'
  return `${tally.rolls} roll${tally.rolls === 1 ? '' : 's'}, ${tally.landed} landed (${Math.round(100 * tally.landed / tally.rolls)}%)`
}

/** "Took 12.4 s of 30 · narrator 9.8 s · skipped the prose rewrite for time", under a line with the dice shown. */
export function paceText(pace: TurnPace): string {
  const slowest = Object.entries(pace.steps).sort((a, b) => b[1] - a[1])[0]
  const skipped = pace.skipped.map((step) => STEP_NAMES[step] ?? step)
  return [`Took ${pace.total.toFixed(1)} s of ${pace.budget}`, slowest ? `${slowest[0]} ${slowest[1].toFixed(1)} s` : '',
    skipped.length ? `skipped ${skipped.join(' and ')} for time` : ''].filter(Boolean).join(' · ')
}

/** The arcs a campaign can start with (dungeon/tiers.py ARCS) and how fast it climbs. */
export const ARC_NAMES: Record<StoryArc, string> = {
  grounded: 'Grounded: stays close to home', classic: 'Classic: from the street to the gods', epic: 'Epic: starts high',
}
export const PACE_NAMES: Record<StoryPace, string> = { slow: 'Slow burn', steady: 'Steady', fast: 'Fast rise' }

/** "Renown: Local, known on their own street (3 of 12)"; the numbers only with the dice shown. */
export function tierText(tier: StoryTier): string {
  const numbers = tier.points === undefined ? '' : tier.next ? ` (${tier.points} of ${tier.next})` : ` (${tier.points})`
  return `${tier.track}: ${tier.tier}, ${tier.words}${numbers}`
}

/** "Corruption: tainted", with "(4 of 10)" when the dice are shown. */
export function darkText(track: SheetGrowth['dark'][number]): string {
  return `${track.name}: ${track.word}${track.points === undefined ? '' : ` (${track.points} of ${track.top})`}`
}

/** The Bonds track in a line: "Bonds: one true bond (1)", the count only with the dice shown. */
export function bondsText(track: SheetBonds): string {
  return `Bonds: ${track.word}${track.count === undefined ? '' : ` (${track.count})`}`
}

/** One bond: "Hesk Aldane (sworn)", or "Hesk Aldane (sworn, broken)" once they turned or died. */
export function bondLine(bond: SheetBonds['bonds'][number]): string {
  return `${bond.name} (${bond.how}${bond.state === 'whole' ? '' : `, ${bond.state}`})`
}

/** How hard the director pushes the story (dungeon/director.py HANDS). */
export const HAND_NAMES: Record<StoryHand, string> = {
  soft: 'Soft: the story waits for you', guiding: 'Guiding: the story comes looking for you', firm: 'Firm: the story moves on schedule',
}

/** "A mystery", "A grudge", "A lead" or "A promise", for a loose end in the journal. */
export function threadKind(kind: JournalThread['kind']): string {
  return { mystery: 'A mystery', grudge: 'A grudge', lead: 'A lead', promise: 'A promise' }[kind]
}

/** The travel-map place a destination is (`journeys` are the map's names), so going there is a journey on foot;
 *  undefined for a place across town or off the map. */
export function journeyTo(journeys: string[], name: string | undefined): string | undefined {
  const bare = (text: string) => text.toLowerCase().replace(/^the\s+/, '')
  return name ? journeys.find((journey) => bare(journey) === bare(name)) : undefined
}

/** A paragraph's sentences, each with its closing punctuation, quotes and following space. */
export function sentences(paragraph: string): string[] {
  return paragraph.match(/[^.!?…]+(?:[.!?…]+["'”’)]*\s*|$)/g) ?? [paragraph]
}

const words = (text: string) => (text.toLowerCase().match(/[\p{L}\p{N}]+/gu) ?? []).join(' ')

/** The sentences of `saved` whose words are not in `draft`: what the checks reworded after the narration streamed
 *  (dungeon/pace.py). Punctuation alone doesn't count, so the always-on em dash fix marks nothing. */
export function reworded(draft: string, saved: string): Set<string> {
  const before = ` ${words(draft)} `
  return new Set(saved.split(/\n{2,}/).flatMap(sentences).filter((sentence) => {
    const said = words(sentence)
    return said && !before.includes(` ${said} `)
  }))
}

/** A turn before any of it has been told. */
export const NO_TURN: TurnSoFar = { stage: null, actions: [], bands: null, rolls: [] }

/** A turn under way with one more of its stream events (dungeon/story.py answer). */
export function turnAfter(turn: TurnSoFar, event: TurnEvent): TurnSoFar {
  if ('stage' in event) return { ...turn, stage: event.stage }
  if ('actions' in event) return { ...turn, actions: event.actions, bands: event.bands ?? null }
  return { ...turn, rolls: [...turn.rolls, event.roll] }
}

export const isShown = (roll: StoryRoll | HiddenRoll): roll is StoryRoll => 'band' in roll

/** "Rolling Allure, hard" while the dice are shown; "Testing your Allure" while they are hidden. */
export function actionLine(action: TurnAction): string {
  return action.difficulty ? `Rolling ${action.stat}, ${action.difficulty.replace('_', ' ')}` : `Testing your ${action.stat}`
}

/** Each band's share of the strip (totals 1 to 100), worst first. */
export function bandSpans(bands: BandStep[]): (BandStep & { from: number; to: number })[] {
  return bands.map((step, index) => ({ ...step, from: index ? (bands[index - 1].ceiling ?? 100) + 1 : 1, to: step.ceiling ?? 100 }))
}

/** Where a total sits on the strip, as a percentage. */
export function markerAt(total: number): number {
  return Math.min(100, Math.max(1, total))
}

/** "2 short of Success at a cost" when the next band up was 5 or fewer away; '' otherwise. */
export function nearMiss(roll: StoryRoll, bands: BandStep[]): string {
  // A critical failure is set by the natural roll, not the total, so it has no step of its own.
  const index = bands.findIndex((step) => step.band === roll.band)
  const ceiling = bands[index]?.ceiling
  if (ceiling === null || ceiling === undefined) return ''
  const short = ceiling + 1 - roll.total
  return short > 0 && short <= 5 ? `${short} short of ${bands[index + 1].label.toLowerCase()}` : ''
}

/** One die on screen: the d100 as a tens and a ones d10, then the stat die and what it added. */
export interface DieFace { key: 'tens' | 'ones' | 'stat' | 'd20' | 'action' | 'challenge1' | 'challenge2' | 'fate1' | 'fate2' | 'fate3' | 'fate4'; sides: number; value: string }
const FATE_KEYS = ['fate1', 'fate2', 'fate3', 'fate4'] as const

/** An Ironsworn roll's two challenge dice, from its card ("Face Danger +iron vs 4 and 9"). */
export function challengeDice(skill: string | null | undefined): [number, number] {
  const found = /vs (\d+) and (\d+)/.exec(skill ?? '')
  return found ? [Number(found[1]), Number(found[2])] : [1, 1]
}

/** The faces the dice land on for a roll the code already made: 100 reads 00 and 0, as percentile dice do. */
export function diceFaces(roll: StoryRoll): DieFace[] {
  if (roll.ruleset === 'fate') return fateFaces(roll.skill).map((value, index) => ({ key: FATE_KEYS[index], sides: 6, value }))
  if (roll.ruleset === 'srd52') return [{ key: 'd20', sides: 20, value: String(roll.natural) }]
  if (roll.ruleset === 'ironsworn') {
    const [first, second] = challengeDice(roll.skill)
    return [{ key: 'action', sides: 6, value: String(roll.natural) }, { key: 'challenge1', sides: 10, value: String(first) },
      { key: 'challenge2', sides: 10, value: String(second) }]
  }
  const faces: DieFace[] = [
    { key: 'tens', sides: 10, value: String(Math.floor((roll.natural % 100) / 10) * 10).padStart(2, '0') },
    { key: 'ones', sides: 10, value: String(roll.natural % 10) },
  ]
  return roll.die && roll.ruleset !== 'brp' ? [...faces, { key: 'stat', sides: roll.die, value: String(roll.bonus) }] : faces
}

/** A face a die shows while it tumbles; `pick` is a number from 0 up to 1. */
export function tumbleFace(face: DieFace, pick: number): string {
  if (face.key.startsWith('fate')) return ['−', '0', '+'][Math.floor(pick * 3)]
  const side = Math.floor(pick * face.sides)
  if (face.key === 'tens') return String(side * 10).padStart(2, '0')
  return String(face.key === 'ones' ? side : side + 1)
}

/** The 3D dice's notation for a roll (src/features/story/dice3d.ts), landing on its faces: its tens die reads 00 as 100 and its d10 reads 0 as 10. */
export function diceNotation(faces: DieFace[]): string {
  const forced = faces.map((face) => {
    const value = Number(face.value)
    if (face.key === 'tens') return value || 100
    return face.key === 'ones' ? value || 10 : value
  })
  return `${faces.map((face) => (face.key === 'tens' ? '1d100' : `1d${face.sides}`)).join('+')}@${forced.join(',')}`
}

const ENDED_BY: Record<string, string> = { place: 'a new place', time: 'time passing', fight: 'the fight ending', quest: 'a quest ending', player: 'you' }

/** A chapter's line in the list: its number, its length, and what ended it (dungeon/chapters.py). */
export function chapterLine(chapter: Pick<StoryChapter, 'number' | 'turns' | 'open' | 'ended_by'>): string {
  const turns = `${chapter.turns} ${chapter.turns === 1 ? 'turn' : 'turns'}`
  if (chapter.open) return `Chapter ${chapter.number} · ${turns} · under way`
  return `Chapter ${chapter.number} · ${turns}${chapter.ended_by ? ` · ended by ${ENDED_BY[chapter.ended_by] ?? 'a break'}` : ''}`
}

/** How a branch in the tree ended, when it was a dead end. */
export function endingText(ending: string): string {
  return ending === 'death' ? ' · ended in death' : ending === 'lost' ? ' · ended with the character lost' : ''
}

/** How an earlier campaign's character comes into a new one (dungeon/legacy.py). */
export const LEGACY_ROLES: Record<LegacyRole, string> = {
  legend: 'A legend: the world remembers them',
  villain: 'A villain: they live on, hidden and turned',
  corpse: 'A corpse: long dead, and only their deeds remain',
}

/** "+3", "-1", "+0". */
export function signed(value: number): string {
  return value < 0 ? String(value) : `+${value}`
}

const ABILITIES: Record<string, string> = { str: 'Str', dex: 'Dex', con: 'Con', int: 'Int', wis: 'Wis', cha: 'Cha' }

/** "Dex 17 (+3), save" for a 5E ability; "save" when the class is proficient in its saving throw. */
export function abilityLine(ability: string, score: number, modifier: number, save: boolean): string {
  return `${ABILITIES[ability] ?? ability} ${score} (${signed(modifier)})${save ? ', save' : ''}`
}

/** "Level 2 · 325 XP, 900 for level 3" (or "the highest level" at 20). */
export function xpLine(level: number, xp: number, next: number | null): string {
  return `Level ${level} · ${xp} XP${next === null ? ', the highest level' : `, ${next} for level ${level + 1}`}`
}

/** "Spell attack +5 · save DC 13 · slots: 1st 1 of 2, 2nd 3 of 3" for a 5E caster. */
export function spellLine(spells: Srd52Spells): string {
  const ordinal = (level: number) => `${level}${level === 1 ? 'st' : level === 2 ? 'nd' : level === 3 ? 'rd' : 'th'}`
  const slots = spells.slots.map((slot) => `${ordinal(slot.level)} ${slot.left} of ${slot.of}`).join(', ')
  return `${spells.ability}: spell attack ${signed(spells.attack)} · save DC ${spells.dc}${slots ? ` · slots: ${slots}` : ''}`
}

/** What BRP characteristics cost to buy: each point over (or under) the start, DEX, INT and POW at their price. */
export function brpCost(characteristics: Record<string, number>, start: number, costly: string[], price: number): number {
  return Object.entries(characteristics).reduce((sum, [stat, value]) => sum + (value - start) * (costly.includes(stat) ? price : 1), 0)
}

/** Whether the standard array is placed on the six abilities, each value once (dungeon/rules/srd52.py build). */
export function arrayPlaced(scores: Record<string, number>, array: number[]): boolean {
  const placed = Object.values(scores).sort((a, b) => b - a)
  return placed.length === array.length && placed.every((value, index) => value === array[index])
}

/** The class's skills a new 5E character can pick, without the ones the background already gives. */
export function skillChoices(from: string[], background: string[]): string[] {
  return from.filter((skill) => !background.includes(skill))
}

/** A skill's id from its name, as the pack writes them ("Sleight of Hand" is sleight-of-hand). */
export function skillId(name: string): string {
  return name.trim().toLowerCase().replaceAll(' ', '-')
}

/** Each turn's receipt by the narration that tells it: the chips sit on the player's line, and show under its reply. */
export function receiptsByReply(messages: StoryMessage[]): Map<string, ReceiptChip[]> {
  const byLine = new Map(messages.filter((message) => message.receipt?.length).map((message) => [message.id, message.receipt ?? []]))
  return new Map(messages.filter((message) => message.role === 'narrator' && message.reply_to && byLine.has(message.reply_to))
    .map((message) => [message.id, byLine.get(message.reply_to ?? '') ?? []]))
}

/** A school or guild in a line: the term, the grades so far and classes missed (dungeon/institutions.py). */
export function institutionLine(item: Pick<JournalInstitution, 'term' | 'grades'>): string {
  if (!item.term) return 'Out of term'
  if (!item.grades) return `${item.term} · no grades yet`
  const missed = item.grades.missed ? ` · ${item.grades.missed} ${item.grades.missed === 1 ? 'class' : 'classes'} missed` : ''
  return `${item.term} · ${item.grades.letter} (${item.grades.gpa.toFixed(1)})${missed}`
}

/** The rest of today's classes, or that there are none. */
export function todayLine(item: Pick<JournalInstitution, 'term' | 'today'>): string {
  if (!item.term) return ''
  return item.today.length ? `Today: ${item.today.map((entry) => `${entry.name} at ${entry.at}`).join(', ')}` : 'No more classes today'
}

interface Town { id: string; name: string; world?: string | null; home?: boolean }

/** The towns to go to that the travel map doesn't show (`journeys` are its names): the other towns of the world the
 *  story is in, A to Z (none until the list holds the town the story is in). A road between towns (`home` false) and a town of another world are not among them. */
export function otherTowns<T extends Town>(cities: T[], here: string, journeys: string[]): T[] {
  const current = cities.find((city) => city.id === here)
  if (!current) return []
  const world = current.world ?? null
  return cities.filter((city) => city.id !== here && city.home !== false && (city.world ?? null) === world && !journeyTo(journeys, city.name))
    .sort((a, b) => a.name.localeCompare(b.name))
}
