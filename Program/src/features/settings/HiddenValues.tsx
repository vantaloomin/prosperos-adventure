import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '../../api'
import { SETTINGS_KEY, useWorkspaceSettings } from '../../workspace'
import type { TableRules, WorkspaceSettings } from '../../types'
import { Toggle } from '../../components/Fields'
import { Notice } from '../../components/Feedback'
import { useTable } from '../story/table'

type Flag = 'adult_side'

function useFlags() {
  const client = useQueryClient()
  const settings = useWorkspaceSettings()
  const [error, setError] = useState('')
  const save = async (change: Partial<Record<Flag, boolean>>) => {
    setError('')
    try {
      client.setQueryData(SETTINGS_KEY, await api<WorkspaceSettings>('/settings', change, 'PUT'))
    }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'That setting was not saved.') }
  }
  return { settings: settings.data, save, error }
}

/** Worlds > Adult side of life (dungeon/world/intimacy.py): off until the user turns it on. */
export function AdultSideSettings() {
  const { settings, save, error } = useFlags()
  return (
    <section className="settings-section form-stack" aria-labelledby="adult-side-heading">
      <div>
        <h2 id="adult-side-heading">Adult side of life</h2>
        <p className="subtle">Real people have a love life and desires of their own. Off until you turn it on.</p>
      </div>
      <Toggle label="Give adults an adult side" checked={settings?.adult_side === true} disabled={!settings} onChange={(checked) => void save({ adult_side: checked })}
        hint="Every adult townsperson gets who they're drawn to, how adventurous they are, their drive and a few things they're into, rolled by the app. Adults only: nobody under 18 ever gets one." />
      {error && <Notice tone="error">{error}</Notice>}
    </section>
  )
}

/** Story > Tone and rules > Dice and hidden values: what shapes the story but stays unseen unless the user turns it on.
 *  This campaign's, kept at the Table (src/features/story/table.ts); the adult side shows only in a world that has it. */
export function HiddenValues() {
  const { rules, save } = useTable()
  const world = useWorkspaceSettings().data
  const [error, setError] = useState('')
  const keep = async (change: Partial<TableRules>) => {
    setError('')
    try { await save(change) }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'That rule was not saved.') }
  }
  return (
    <section className="settings-section form-stack" aria-labelledby="hidden-values-heading">
      <div>
        <h2 id="hidden-values-heading">Dice and hidden values</h2>
        <p className="subtle">Some things stay behind the curtain: you notice them from how the story goes, not from a label.</p>
      </div>
      <Toggle label="Show the dice" checked={rules?.show_odds === true} disabled={!rules} onChange={(checked) => void keep({ show_odds: checked })}
        hint="Each roll under your line: the stat, the die, the difficulty and how it landed. Off, you feel the dice only through the story." />
      {rules?.show_odds && (
        <Toggle label="Roll the dice on screen" checked={rules.roll_dice} onChange={(checked) => void keep({ roll_dice: checked })}
          hint="3D dice roll across the story and land on each roll before its result shows (flat dice on a PC without 3D graphics). The game has already rolled them: what you see is that roll, never a new one. A click lands them at once." />
      )}
      {world?.adult_side && rules && (
        <Toggle label="Show townsfolk's adult side" checked={rules.show_adult_side} onChange={(checked) => void keep({ show_adult_side: checked })}
          hint="Who each person is drawn to, how adventurous they are and what they're into." />
      )}
      {error && <Notice tone="error">{error}</Notice>}
    </section>
  )
}
