import { useState } from 'react'
import { api } from '../../api'
import { Notice } from '../../components/Feedback'
import { TextInput } from '../../components/Fields'
import { ModelCombobox } from './models/ModelCombobox'
import type { DiscoveredModel } from './models/discovery'

interface ImageModelList { ok: boolean; error: string | null; models: { id: string; name: string }[] }
interface Connection { provider: string; baseUrl: string; apiKey: string; backendId?: string }

/** The provider's image models, fetched on request. A list belongs to the provider, address and key it was
 * fetched with, so changing any of them sets it aside. */
function useImageModels({ provider, baseUrl, apiKey, backendId }: Connection) {
  const [list, setList] = useState<{ for: string; result: ImageModelList } | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const connection = `${provider}\n${baseUrl.trim()}\n${apiKey}`
  const needsAddress = provider === 'other' && !baseUrl.trim()
  const fetchList = async () => {
    if (busy || needsAddress) return
    setBusy(true)
    setError('')
    try {
      const result = await api<ImageModelList>('/images/models', { provider, base_url: baseUrl.trim(), api_key: apiKey, backend_id: backendId ?? null })
      setList({ for: connection, result })
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'The models were not listed.') } finally { setBusy(false) }
  }
  return { current: list?.for === connection ? list.result : null, busy, error, needsAddress, fetchList }
}

const asDiscovered = (list: ImageModelList | null): DiscoveredModel[] =>
  (list?.models ?? []).map((model) => ({ ...model, context_tokens: null, max_output_tokens: null, limit_source: 'unreported' }))

/**
 * An image API's model, picked from the provider's own list once it is fetched (as a text model's Connect does),
 * or typed. A saved backend's key is used when none is typed, for the address it was saved for only
 * (dungeon/images/routes.py).
 */
export function ImageModelField({ value, placeholder, onChange, ...connection }: Connection & { value: string; placeholder?: string; onChange: (value: string) => void }) {
  const { current, busy, error, needsAddress, fetchList } = useImageModels(connection)
  const models = asDiscovered(current)
  return <>
    <div className="form-actions">
      <button type="button" className="button" aria-disabled={busy || needsAddress} onClick={() => void fetchList()}>{listLabel(busy, Boolean(current))}</button>
      <span className="subtle">{needsAddress ? 'Enter the API base URL first.' : 'Asks the provider which image models it has. Nothing is made.'}</span>
    </div>
    <ListStatus error={error || current?.error || ''} empty={Boolean(current?.ok) && models.length === 0} />
    {models.length > 0 && <ModelCombobox models={models} value={models.some((model) => model.id === value) ? value : ''} onChange={onChange} />}
    <TextInput label="Image model" value={value} required onChange={onChange} placeholder={placeholder}
      hint="Choose from the list, or type the model's exact name from the provider's documentation." />
  </>
}

const listLabel = (busy: boolean, listed: boolean) => busy ? 'Listing models…' : listed ? 'List models again' : 'List models'

function ListStatus({ error, empty }: { error: string; empty: boolean }) {
  if (error) return <Notice tone="error">{error}</Notice>
  return empty ? <p className="subtle">The provider listed no image models. Type the model name below.</p> : null
}
