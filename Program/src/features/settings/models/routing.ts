import type { ModelsOverview } from './types.ts'

/** What a job's selector shows: its own profile, or the conversation profile it falls back to. */
export function jobChoice(overview: ModelsOverview, job: string): { value: string; inherited: string | null } {
  const own = overview.routes[job] ?? ''
  const chat = overview.profiles.find(profile => profile.id === overview.routes.chat)
  return { value: own, inherited: job === 'chat' || own ? null : chat?.name ?? null }
}

