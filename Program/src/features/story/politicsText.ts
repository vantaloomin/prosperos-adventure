import type { PoliticsFaction, PoliticsIssue, PoliticsLevel, PoliticsRelation, PoliticsStage, TownPolitics } from '../../types'

const STAGES: Record<PoliticsStage, string> = {
  whispers: 'Whispers', open: 'Out in the open', heated: 'Heated', settled: 'Settled', ended: 'Over',
}

/** "Heated", or "Real history" for a real question of the city's year (it stays open). */
export function stageLabel(issue: Pick<PoliticsIssue, 'stage' | 'real'>): string {
  return issue.real && issue.stage !== 'ended' ? `${STAGES[issue.stage]} · real history` : STAGES[issue.stage]
}

/** The five views as a select lists them, strongest for the first side first. */
export function viewOptions(issue: Pick<PoliticsIssue, 'sides'>): { value: number; label: string }[] {
  const [first, second] = issue.sides
  return [
    { value: 2, label: `Strongly: ${first.name}` }, { value: 1, label: `Leans: ${first.name}` },
    { value: 0, label: "Doesn't much care" },
    { value: -1, label: `Leans: ${second.name}` }, { value: -2, label: `Strongly: ${second.name}` },
  ]
}

/** "Strongly: Dry", "Leans: Wet" or "Doesn't much care" (matches dungeon/world/politics.py view_label). */
export function viewLabel(view: number, issue: Pick<PoliticsIssue, 'sides'>): string {
  return viewOptions(issue).find((option) => option.value === view)?.label ?? "Doesn't much care"
}

/** Whole-number shares of the town for each side and of those who don't much care, adding up to 100. */
export function splitShares(split: PoliticsIssue['split']): { first: number; second: number; neither: number } {
  const total = split.first + split.second + split.neither
  if (!total) return { first: 0, second: 0, neither: 100 }
  const first = Math.round((100 * split.first) / total)
  const second = Math.round((100 * split.second) / total)
  return { first, second, neither: Math.max(100 - first - second, 0) }
}

/** "Around town: 35% Wet, 23% Dry, 42% don't much care." */
export function splitText(issue: Pick<PoliticsIssue, 'sides' | 'split'>): string {
  const shares = splitShares(issue.split)
  return `Around town: ${shares.first}% ${issue.sides[0].name}, ${shares.second}% ${issue.sides[1].name}, ${shares.neither}% don't much care.`
}

/** "47% don't much care", the line under the bar; the sides' shares sit at its ends. */
export function neitherText(split: PoliticsIssue['split']): string {
  return `${splitShares(split).neither}% don't much care`
}

/** People with a view first, strongest first; those who don't much care fold away when there are more than 3. */
export function sortedPeople<T extends { views: Record<string, { view: number }> }>(people: T[], issueId: string): { shown: T[]; folded: T[] } {
  const strength = (person: T) => Math.abs(person.views[issueId]?.view ?? 0)
  const sorted = [...people].sort((a, b) => strength(b) - strength(a))
  const caring = sorted.filter((person) => strength(person) > 0)
  const rest = sorted.filter((person) => strength(person) === 0)
  return rest.length > 3 ? { shown: caring, folded: rest } : { shown: sorted, folded: [] }
}

export const STAGE_CHOICES: { value: string; label: string }[] = [
  { value: 'whispers', label: STAGES.whispers }, { value: 'open', label: STAGES.open }, { value: 'heated', label: STAGES.heated },
]

const PULL = ['', 'Little pull', 'Some pull', 'Real pull', 'Strong pull', 'Runs the town']

/** "Strong pull, up after a win" or "Some pull". */
export function pullText(faction: Pick<PoliticsFaction, 'pull' | 'change'>): string {
  const label = PULL[Math.min(Math.max(faction.pull, 1), 5)]
  if (faction.change > 0) return `${label}, up after a win`
  return faction.change < 0 ? `${label}, down after a loss` : label
}

export const STANCES: { value: number; label: string }[] = [
  { value: 2, label: 'Allies' }, { value: 1, label: 'Friendly' }, { value: 0, label: 'Keep their distance' },
  { value: -1, label: 'Rivals' }, { value: -2, label: 'At open odds' },
]

export function stanceLabel(stance: number): string {
  return STANCES.find((item) => item.value === stance)?.label ?? 'Keep their distance'
}

/** How a faction stands with each other faction, from the pairs the app lists once each way. */
export function relationsOf(id: string, relations: PoliticsRelation[]): { other: string; stance: number; by: PoliticsRelation['by'] }[] {
  return relations.filter((link) => link.a === id || link.b === id)
    .map((link) => ({ other: link.a === id ? link.b : link.a, stance: link.stance, by: link.by }))
}

/** "Allies: The Anti-Saloon League. Rivals: Tammany Hall." Factions keeping their distance are left out. */
export function alliesText(id: string, data: Pick<TownPolitics, 'relations' | 'factions'>): string {
  const names = new Map(data.factions.map((faction) => [faction.id, faction.name]))
  const links = relationsOf(id, data.relations).filter((link) => names.has(link.other))
  const group = (test: (stance: number) => boolean) => links.filter((link) => test(link.stance)).map((link) => names.get(link.other)).join(', ')
  const allies = group((stance) => stance > 0)
  const rivals = group((stance) => stance < 0)
  return [allies && `Allies: ${allies}.`, rivals && `Rivals: ${rivals}.`].filter(Boolean).join(' ')
}

/** "Backing Wet: Tammany Hall, The garment unions." for each side some faction backs. */
export function backingText(issue: Pick<PoliticsIssue, 'sides' | 'lines'>, factions: Pick<PoliticsFaction, 'id' | 'name'>[]): string[] {
  return issue.sides.map((side, index) => {
    const names = factions.filter((faction) => issue.lines[faction.id] === index).map((faction) => faction.name)
    return names.length ? `Backing ${side.name}: ${names.join(', ')}.` : ''
  }).filter(Boolean)
}

/** "It went the way of those who wanted to build the pier." for a settled issue, or null. */
export function outcomeText(issue: Pick<PoliticsIssue, 'settled'>): string | null {
  const settled = issue.settled
  if (!settled) return null
  const label = settled.options.find((option) => option.option === settled.picked)?.label ?? ''
  return settled.picked_by === 'user' ? `${label} You picked how it went.` : label
}

/** The outcome select's value: '' while the app decides, else the side that won or 2 for fizzled out. */
export function outcomeChoices(issue: Pick<PoliticsIssue, 'sides'>): { value: string; label: string }[] {
  return [
    { value: '', label: 'Let the dice decide' },
    { value: '0', label: `${issue.sides[0].name} won` }, { value: '1', label: `${issue.sides[1].name} won` },
    { value: '2', label: 'It fizzled out' },
  ]
}

/** The Table's Local politics rule (dungeon/politics.py LEVELS). */
export const POLITICS_LEVELS: { value: PoliticsLevel; label: string; hint: string }[] = [
  { value: 'off', label: 'Off', hint: 'Nobody argues about local politics.' },
  { value: 'quiet', label: 'Quiet', hint: 'One big question of the day, and a local quarrel now and then.' },
  { value: 'true_to_life', label: 'True to life', hint: 'The big questions of the day, and local quarrels that come and go: people take sides by their work and character.' },
  { value: 'lively', label: 'Lively', hint: 'Always something to argue about: up to three big questions, and local quarrels come often.' },
]

/** "Aug 19", a beat's day; the story's calendar is the world's, so no weekday and no year. */
export function beatDate(day: string): string {
  const [year, month, date] = day.split('-').map(Number)
  if (!year || !month || !date) return day
  return `${['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][month - 1]} ${date}`
}
