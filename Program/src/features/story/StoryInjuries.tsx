import { useState } from 'react'
import type { InjuryPersistence } from '../../types'
import { Field } from '../../components/Fields'
import { Notice } from '../../components/Feedback'
import { useTable } from './table'

const CHOICES: [InjuryPersistence, string][] = [['permanent', 'Permanent: they stay'],
  ['temporary', 'Temporary: they fade with time'], ['none', 'None: wounds heal clean']]

/** Injury persistence (dungeon/injuries.py): whether a maiming leaves a lasting injury, and whether it stays. */
export function StoryInjuries({ persistence, onSaved }: { persistence: InjuryPersistence; onSaved: () => void }) {
  const { save: keep } = useTable()
  const [error, setError] = useState('')
  const save = async (value: InjuryPersistence) => {
    setError('')
    try { await keep({ injury_persistence: value }); onSaved() }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'That setting was not saved.') }
  }
  return (<>
    <Field label="Lasting injuries" hint="A maiming or a critical hit can leave a lost eye, a limp or a scar that makes some things harder and that people notice.">
      {(id, describedBy) => <select id={id} value={persistence} aria-describedby={describedBy}
        onChange={(event) => void save(event.target.value as InjuryPersistence)}>
        {CHOICES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select>}
    </Field>
    {error && <Notice tone="error">{error}</Notice>}
  </>)
}
