import type { BackupEntry } from '../../types'

export function backupSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

const KINDS: Record<BackupEntry['kind'], string> = {
  backup: 'Backup', 'pre-upgrade': 'Before an upgrade', 'before-reset': 'Before starting over', 'before-delete': 'Before deleting', 'before-debug': 'Before debug time', auto: 'Automatic',
}

/** One line describing a backup in the list; names the ones the app made on its own. */
export function backupLabel(entry: BackupEntry, formatDate: (iso: string) => string): string {
  if (!entry.readable) return `${entry.name} (cannot be read)`
  const when = entry.created_at ? formatDate(entry.created_at) : entry.name
  const kind = KINDS[entry.kind]
  return `${kind}, ${when} (${backupSize(entry.bytes)})`
}
