import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api'
import { Notice } from '../../components/Feedback'
import { TextArea } from '../../components/Fields'
import { groupPrompts, placeholderHint, type EditablePrompt } from './prompts'
import { SectionPending } from '../../components/SectionPending'

const KEY = ['prompts']

/** Settings > Developer: the core prompts sent to the user's models, each with its default (dungeon/prompt_library.py). */
export function PromptSettings() {
  const prompts = useQuery({ queryKey: KEY, queryFn: () => api<EditablePrompt[]>('/prompts') })
  if (!prompts.data) return <SectionPending queries={[prompts]} heading="prompts-heading" title="Prompts" />
  return (
    <section className="settings-section form-stack" aria-labelledby="prompts-heading">
      <div>
        <h2 id="prompts-heading">Prompts</h2>
        <p className="subtle">The instructions your models are given. Changes apply to the next request, and Reset to default brings back the shipped wording. Words in double braces, such as {'{{name}}'}, are filled in by the app and must stay. Staying in character, OOC answers and the picture safety check are handled by the app too, so they keep working whatever a prompt says.</p>
      </div>
      {groupPrompts(prompts.data).map(([group, items]) => (
        <div key={group} className="form-stack">
          <h3>{group}</h3>
          {items.map((prompt) => <PromptEditor key={prompt.name} prompt={prompt} />)}
        </div>
      ))}
    </section>
  )
}

function PromptEditor({ prompt }: { prompt: EditablePrompt }) {
  const client = useQueryClient()
  const [text, setText] = useState(prompt.text)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<{ tone: 'info' | 'error'; text: string } | null>(null)
  const run = async (request: () => Promise<EditablePrompt>, done: string) => {
    setBusy(true)
    try {
      const saved = await request()
      setText(saved.text)
      client.setQueryData<EditablePrompt[]>(KEY, (current) => current?.map((item) => item.name === saved.name ? saved : item))
      setResult({ tone: 'info', text: done })
    } catch (error) {
      setResult({ tone: 'error', text: error instanceof Error ? error.message : 'Not saved.' })
    } finally { setBusy(false) }
  }
  const save = () => run(() => api<EditablePrompt>(`/prompts/${prompt.name}`, { text }, 'PUT'), 'Saved. The next request uses it.')
  const reset = () => run(() => api<EditablePrompt>(`/prompts/${prompt.name}`, undefined, 'DELETE'), 'Back to the default wording.')
  return (
    <details className="prompt-editor">
      <PromptSummary prompt={prompt} />
      <TextArea label={prompt.label} value={text} onChange={setText} rows={14} maxLength={20000}
        hint={<>{prompt.description}{prompt.placeholders.length > 0 && <> {placeholderHint(prompt)}</>}</>} />
      {result && <Notice tone={result.tone}>{result.text}</Notice>}
      <div className="form-actions">
        <button type="button" className="button primary" disabled={busy || !text.trim() || text === prompt.text} onClick={() => void save()}>Save</button>
        {prompt.customized && <button type="button" className="button" disabled={busy} onClick={() => void reset()}>Reset to default</button>}
        {text !== prompt.text && <button type="button" className="text-button" disabled={busy} onClick={() => setText(prompt.text)}>Discard changes</button>}
      </div>
      {prompt.customized && <DefaultWording text={prompt.default} />}
    </details>
  )
}

function PromptSummary({ prompt }: { prompt: EditablePrompt }) {
  return (
    <>
      <summary>{prompt.label}{prompt.customized && <span className="badge">Your wording</span>}{prompt.outdated && <span className="badge">New default</span>}</summary>
      {prompt.outdated && <Notice tone="info">An update changed the default for this prompt. Your wording is kept; compare it with the new default below, or reset to use it.</Notice>}
    </>
  )
}

function DefaultWording({ text }: { text: string }) {
  return (
    <details className="prompt-default">
      <summary>Default wording</summary>
      <pre>{text}</pre>
    </details>
  )
}
