import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api'
import type { Story, TableRules } from '../../types'

export const STORY_KEY = ['story']

/** The Table (dungeon/table.py): this campaign's rules, kept with the campaign so they never follow you to another
 *  world. A new campaign starts in the world's tone and with your last choices for what is shown. Read from the story,
 *  so whatever reloads the story (a new story, another world) reloads the rules with it. */
export function useTable() {
  const client = useQueryClient()
  const rules = useQuery({ queryKey: STORY_KEY, queryFn: () => api<Story>('/story'), select: (story) => story.table })
  const save = async (change: Partial<TableRules>) => {
    const saved = await api<TableRules>('/story/table', change, 'PUT')
    client.setQueryData<Story>(STORY_KEY, (story) => story && { ...story, table: saved })
    // The story carries its rolls, tone and record by these rules, so what shows them is read again.
    await Promise.all(['story', 'story-journal', 'story-gm'].map((key) => client.invalidateQueries({ queryKey: [key] })))
  }
  return { rules: rules.data, save }
}
