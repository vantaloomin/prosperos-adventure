import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../../api'

export interface LocalProgram {
  program: 'lmstudio' | 'ollama' | 'kobold' | 'comfyui'
  label: string
  address: string
  used_by: { kind: 'profile' | 'image'; id: string; name: string }[]
  path: string
  path_chosen: boolean
  model_path: string
  needs_model: boolean
  state: 'idle' | 'starting' | 'running' | 'failed'
  message: string
  /** The system's own reason a start failed, shown small under the message. */
  detail?: string
}
export interface LauncherView { auto_launch: boolean; system: 'windows' | 'mac' | 'linux'; programs: LocalProgram[] }

export const LAUNCHER_KEY = ['launcher']

/** The local programs in use (dungeon/launcher.py), asked again every few seconds while one is starting. */
export function useLauncher(enabled = true) {
  const client = useQueryClient()
  const query = useQuery({
    queryKey: LAUNCHER_KEY, enabled, queryFn: () => api<LauncherView>('/models/launcher'),
    refetchInterval: (state) => state.state.data?.programs.some(item => item.state === 'starting') ? 2000 : false,
  })
  const send = async (path: string, body: unknown, method?: string) => client.setQueryData(LAUNCHER_KEY, await api<LauncherView>(path, body, method))
  return {
    query,
    launch: (program: string) => send(`/models/launcher/${program}/launch`, {}),
    choose: (program: string, body: { path?: string; model_path?: string }) => send(`/models/launcher/${program}`, body, 'PUT'),
    setAuto: (auto_launch: boolean) => send('/models/launcher', { auto_launch }, 'PUT'),
  }
}

export const STATE_TEXT: Record<LocalProgram['state'], string> = { idle: 'Not running.', starting: 'Starting…', running: 'Running.', failed: 'Did not start.' }

/** The program a profile or image backend uses, when the Dungeon can start it. */
export function programFor(view: LauncherView | undefined, id: string): LocalProgram | undefined {
  return view?.programs.find(item => item.used_by.some(use => use.id === id))
}
