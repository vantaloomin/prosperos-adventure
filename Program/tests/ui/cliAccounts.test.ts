import assert from 'node:assert/strict'
import { test } from 'node:test'
import { accountLabel, sameAccount, signInStep, type CliAccount } from '../../src/features/settings/models/cliAccounts.ts'

const usual: CliAccount = { provider: 'claude_code', account_dir: '', commands: ['claude'], sources: [], signed_in: true, email: 'one@example.com' }
const second: CliAccount = { provider: 'claude_code', account_dir: 'C:\\Users\\Jim\\.claude-account2', commands: ['claude2'], sources: [], signed_in: false, email: '' }
const folderOnly: CliAccount = { provider: 'codex', account_dir: '/home/jim/.codex-work', commands: [], sources: [], signed_in: false, email: '' }

test('each account is named by its command, else its folder, with the email the CLI reports', () => {
  assert.equal(accountLabel(usual), 'claude (usual account) · one@example.com')
  assert.equal(accountLabel(second), 'claude2')
  assert.equal(accountLabel(folderOnly), '.codex-work')
})

test('a typed folder matches its account whatever its slashes, case or trailing slash', () => {
  assert.ok(sameAccount(second, 'c:/users/jim/.claude-account2/'))
  assert.ok(sameAccount(usual, undefined) && sameAccount(usual, '  '))
  assert.ok(!sameAccount(usual, second.account_dir))
})

test('signing in uses the account’s own command, else the CLI with its folder set', () => {
  assert.equal(signInStep(second, true), 'claude2')
  assert.equal(signInStep({ ...folderOnly, commands: ['codex2'] }, false), 'codex2 login')
  assert.equal(signInStep(folderOnly, false), 'CODEX_HOME="/home/jim/.codex-work" codex login')
  assert.equal(signInStep({ ...second, commands: [] }, true), '$env:CLAUDE_CONFIG_DIR="C:\\Users\\Jim\\.claude-account2"; claude')
  assert.equal(signInStep(usual, true), 'claude')
})
