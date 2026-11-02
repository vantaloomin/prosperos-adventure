import { useState } from 'react'
import type { LegacyRole, StoryArc, StoryHand, StoryPace, StoryStart as StartChoices, TablePreset } from '../../types'

export type Legacy = { world_id: string; role: LegacyRole }
export type Campaign = { arc: StoryArc | null; pace: StoryPace | null; ironman: boolean; legacy: Legacy | null }

const NO_CAMPAIGN: Campaign = { arc: null, pace: null, ironman: false, legacy: null }

/** Session zero (docs/story.md "The Table"), as the cast page asks it: a tone preset (the world's own first, so
 *  Begin is one click away) and, behind Options (./CampaignOptions.tsx), what is chosen once for the whole campaign.
 *  The rest of the tone, the narration format and what is shown of the dice start as the preset and the player's
 *  last campaign set them, and change in play under Tone and rules. */
export function useSession(choices: StartChoices) {
  const presets = choices.presets ?? []
  const [presetId, setPresetId] = useState(presets[0]?.id ?? '')
  const [hand, setHand] = useState<StoryHand | null>(null)
  const [campaign, setCampaign] = useState<Campaign>(NO_CAMPAIGN)
  const preset = presets.find((item) => item.id === presetId) ?? presets[0]
  const steer = hand ?? steerOf(preset, choices)
  return {
    presets, presetId: preset?.id ?? '', pick: (id: string) => { setPresetId(id); setHand(null) },
    steer, setHand, campaign, setCampaign, body: sessionBody(preset, campaign, choices.arc ? steer : null),
  }
}

export type Session = ReturnType<typeof useSession>

/** The director's hand a preset sets, else the world's own. */
function steerOf(preset: TablePreset | undefined, choices: StartChoices): StoryHand {
  return preset?.hand ?? choices.arc?.hand ?? 'guiding'
}

/** The start request's share of session zero: the preset's rules, and only the campaign choices the player made. */
export function sessionBody(preset: TablePreset | undefined, campaign: Campaign, hand: StoryHand | null): Record<string, unknown> {
  const { ironman, ...rest } = campaign
  const chosen = Object.fromEntries(Object.entries({ ...rest, hand }).filter(([, value]) => value))
  return { table: { ...preset?.rules }, ...chosen, ironman }
}
