import type { StoryFaction, StoryTier } from '../../types'
import { tierText } from './storyText'
import { EntityName } from './EntityCard'
import { ThingIcon } from './StoryGear'

/** Your character's tier (dungeon/tiers.py) and the factions they know of (dungeon/factions.py), with how you stand
 * with each. */
export function StoryPowers({ factions, tier, open }: { factions: StoryFaction[]; tier?: StoryTier | null; open?: boolean }) {
  if (!factions.length && !tier) return null
  return (
    <details className="story-people" open={open}>
      <summary>Powers ({factions.length})</summary>
      {tier && <p className="subtle">{tierText(tier)}</p>}
      <ul>
        {factions.map((faction) => <li key={faction.id}>
          <p className="story-thing"><ThingIcon src={faction.emblem} /><span><strong><EntityName entity={{ kind: 'faction', id: faction.id }}>{faction.name}</EntityName></strong> <span className="subtle">· you are {faction.standing} to them</span></span></p>
          <p className="subtle">{faction.summary}</p>
        </li>)}
      </ul>
    </details>
  )
}
