// The Claude Code and Codex accounts found on this PC (claude, claude2, codex2…), so a profile can pick one.
import type { Provider } from './types'

export interface CliAccount { provider: Provider; account_dir: string; commands: string[]; sources: string[]; signed_in: boolean; email: string }

const plain = (folder: string) => folder.trim().replace(/[\\/]+$/, '').replace(/\\/g, '/').toLowerCase()

/** Whether a profile's account folder is this account ('' is the usual account). */
export const sameAccount = (account: CliAccount, folder: string | undefined) => plain(account.account_dir) === plain(folder ?? '')

const folderName = (folder: string) => folder.split(/[\\/]/).filter(Boolean).pop() ?? folder

/** The account's button: its command (claude2), else its folder's name, with the email Claude Code reports. */
export function accountLabel(account: CliAccount): string {
  const name = account.commands[0] ?? folderName(account.account_dir)
  const usual = account.account_dir ? '' : ' (usual account)'
  return `${name}${usual}${account.email ? ` · ${account.email}` : ''}`
}

/** How to sign in to an account that is not signed in yet, as a command for this computer's terminal: its own
 * command (claude2) when it has one, else the CLI with the account's folder set. */
export function signInStep(account: CliAccount, windows: boolean): string {
  const base = account.provider === 'codex' ? 'codex' : 'claude'
  const login = account.provider === 'codex' ? ' login' : ''
  const wrapper = account.commands.find(command => command !== base)
  if (wrapper) return wrapper + login
  if (!account.account_dir) return base + login
  const variable = account.provider === 'codex' ? 'CODEX_HOME' : 'CLAUDE_CONFIG_DIR'
  return windows ? `$env:${variable}="${account.account_dir}"; ${base}${login}` : `${variable}="${account.account_dir}" ${base}${login}`
}
