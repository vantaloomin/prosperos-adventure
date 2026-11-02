import { useState } from 'react'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { needed, quality, roomy, size, type ReadyView } from './readyText'
import { useReadyActions } from './useReady'

/** The one question the app asks before it sets things up: the model, its quality and how much it downloads. */
export function ConfirmDownload({ view, onClose }: { view: ReadyView; onClose: () => void }) {
  const actions = useReadyActions()
  const [error, setError] = useState('')
  const model = view.pick
  const total = needed(view)
  const fits = roomy(view)
  const confirm = async () => {
    try { await actions.start(model.key); onClose() } catch (failure) { setError(failure instanceof Error ? failure.message : 'The download did not start.') }
  }
  return (
    <ConfirmDialog title={`Download ${model.name}?`} onClose={onClose} actions={<>
      <button type="button" className="button primary" disabled={!fits} onClick={() => void confirm()}>Download {size(total)}</button>
      <button type="button" className="button" autoFocus onClick={onClose}>Not now</button>
    </>}>
      <p>{view.card ? `It runs on your ${view.card.name} (${Math.round(view.card.memory_gb)} GB), on this computer.` : 'It runs on this computer.'} Nothing you write leaves it.</p>
      <dl className="download-facts">
        <div><dt>Model</dt><dd>{model.name}</dd></div>
        <div><dt>Quality</dt><dd>{model.quant}, {quality(model.quant)}</dd></div>
        <div><dt>Download</dt><dd>{size(model.bytes)}</dd></div>
        {view.runtime_bytes > 0 && <div><dt>Also downloads</dt><dd>llama.cpp, {size(view.runtime_bytes)}</dd></div>}
        {view.free_bytes !== null && <div className={fits ? undefined : 'short'}><dt>Space on {view.drive}</dt><dd>{size(view.free_bytes)} free</dd></div>}
        <div><dt>License</dt><dd><a href={model.page} target="_blank" rel="noreferrer">{model.licence}</a></dd></div>
      </dl>
      {!fits && view.free_bytes !== null && <p className="download-short" role="alert">Needs about {size(total + 2e9)} free on {view.drive}: the download plus room to set it up. It has {size(view.free_bytes)}. Free up some space, then try again.</p>}
      <p className="subtle">You can set up your story while it downloads. If you close the app, it picks up where it left off.</p>
      {error && <p className="download-short" role="alert">{error}</p>}
    </ConfirmDialog>
  )
}
