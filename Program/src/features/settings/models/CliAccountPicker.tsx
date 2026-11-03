// Settings > Models: pick which Claude or ChatGPT account a Claude Code or Codex profile uses, from the accounts
// found on this PC (adventure/providers/cli_accounts.py).
import { useQuery } from '@tanstack/react-query'
import { RefreshCw } from 'lucide-react'
import { api } from '../../../api'
import { shownPath } from '../../../paths'
import { accountLabel, sameAccount, signInStep, type CliAccount } from './cliAccounts'
import type { Provider } from './types'

const WINDOWS = typeof navigator !== 'undefined' && /win/i.test(navigator.platform)

export function CliAccountPicker({ provider, value, onPick }: { provider: Provider; value?: string; onPick: (folder: string) => void }) {
  // Each account's sign-in is asked of its CLI, which takes a moment, so the list is kept while Settings is open.
  const query = useQuery({ queryKey: ['cli-accounts'], queryFn: () => api<{ accounts: CliAccount[] }>('/models/cli-accounts'), staleTime: 5 * 60_000 })
  const busy = query.isFetching
  const look = () => query.refetch()
  const accounts = query.data?.accounts ?? (query.isError ? [] : null)
  if (accounts === null) return <p className="subtle">Looking for accounts on this computer…</p>
  const mine = accounts.filter(account => account.provider === provider)
  const chosen = mine.find(account => sameAccount(account, value))
  const again = <button type="button" className="button" disabled={busy} onClick={() => void look()}><RefreshCw size={15} aria-hidden="true" />{busy ? 'Looking…' : 'Look again'}</button>
  if (!mine.length) return <div className="form-actions"><span className="subtle">No {provider === 'codex' ? 'Codex' : 'Claude Code'} accounts found on this computer.</span>{again}</div>
  return <>
    <fieldset className="provider-picker cli-accounts"><legend>Account</legend>
      {mine.map(account => <button key={account.account_dir || 'usual'} type="button" className={`button${account === chosen ? ' selected' : ''}`} aria-pressed={account === chosen}
        title={account.account_dir ? shownPath(account.account_dir) : undefined} onClick={() => onPick(account.account_dir)}>{accountLabel(account)}{account.signed_in ? '' : ' (not signed in)'}</button>)}
      {again}
    </fieldset>
    <AccountNote chosen={chosen} />
  </>
}

function AccountNote({ chosen }: { chosen?: CliAccount }) {
  if (!chosen) return <p className="subtle">Found from your claude and codex commands (such as claude2), your PowerShell profile and account folders. Pick one, or type a folder below.</p>
  if (!chosen.signed_in) return <p className="subtle">This account is not signed in. Run <code>{signInStep(chosen, WINDOWS)}</code> in a terminal and sign in, then look again.</p>
  return <p className="subtle">{chosen.account_dir ? `Uses the account kept in ${shownPath(chosen.account_dir)}.` : 'Uses the account the CLI is usually signed in to.'}</p>
}
