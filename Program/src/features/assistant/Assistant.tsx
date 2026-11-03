import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode } from 'react'
import { ArrowUp, Lightbulb, RotateCcw, Undo2, X } from 'lucide-react'
import type { View } from '../../workspace'
import { Notice } from '../../components/Feedback'
import { AiFooter } from '../../components/Safety'
import { after, before, comparable, effect, GM_KINDS, title, type Proposal } from './proposals'
import { assistant } from './store'
import { useAssistantChat, type AssistantChat } from './useAssistantChat'

const NO_MODEL = 'Settings > Models'

/** The Sidebar Assistant, after the sidecar in Prospero's Companion: an out-of-story chat beside the app that sees the
 * story and proposes changes the user applies one by one (adventure/assistant.py). */
export function Assistant({ view, go }: { view: View; go: (view: View) => void }) {
  const chat = useAssistantChat(view)
  return (
    <aside className="sidecar" aria-labelledby="assistant-title">
      <header>
        <div>
          <h2 id="assistant-title"><Lightbulb aria-hidden="true" />Sidebar Assistant</h2>
          <p className="subtle">Only you see this. Nothing here reaches the narrator.</p>
        </div>
        <div className="sidecar-header-actions">
          {chat.turns.length > 0 && <button type="button" className="icon-button" aria-label="Start a new chat with the assistant" title="Start over" onClick={chat.clear}><RotateCcw aria-hidden="true" /></button>}
          <button type="button" className="icon-button" aria-label="Close the Sidebar Assistant" onClick={() => assistant.setOpen(false)}><X aria-hidden="true" /></button>
        </div>
      </header>
      <Transcript chat={chat} />
      <Composer chat={chat} openModels={() => go('settings/models')} />
    </aside>
  )
}

function Transcript({ chat }: { chat: AssistantChat }) {
  const transcript = useRef<HTMLDivElement>(null)
  useEffect(() => { transcript.current?.scrollTo({ top: transcript.current.scrollHeight }) }, [chat.turns.length, chat.busy])
  return (
    <div className="sidecar-transcript" ref={transcript} aria-live="polite">
      {chat.turns.length === 0 && <Welcome />}
      {chat.turns.map((turn) => (
        <article key={turn.id} className="sidecar-turn">
          <div className="sidecar-message">{turn.message.length > 600 ? `${turn.message.slice(0, 600)}…` : turn.message}</div>
          <p className="sidecar-reply">{turn.reply}</p>
          {turn.proposals.map((proposal) => <ProposalCard key={proposal.id} proposal={proposal} onApply={() => chat.apply(proposal)} onUndo={() => chat.undo(proposal)} onDismiss={() => chat.dismiss(proposal)} />)}
          {turn.proposals.filter((proposal) => proposal.status === 'pending').length > 1 && <button type="button" className="button" onClick={() => void chat.applyAll(turn)}>Apply all</button>}
        </article>
      ))}
      {chat.busy && <Notice>Thinking it over. A local model can take a minute or two.</Notice>}
    </div>
  )
}

function Composer({ chat, openModels }: { chat: AssistantChat; openModels: () => void }) {
  const [message, setMessage] = useState('')
  const send = async (event?: FormEvent) => {
    event?.preventDefault()
    const text = message.trim()
    if (text && !chat.busy && await chat.send(text)) setMessage('')
  }
  const keyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) { event.preventDefault(); void send() }
  }
  const { focus } = chat
  const settings = chat.error.includes(NO_MODEL) && <button type="button" className="text-button" onClick={openModels}>Open Settings</button>
  return (
    <form className="sidecar-composer" onSubmit={(event) => void send(event)}>
      {focus && <p className="sidecar-focus"><span>About the passage: &ldquo;{focus.text.length > 90 ? `${focus.text.slice(0, 90)}…` : focus.text}&rdquo;</span><button type="button" className="icon-button" aria-label="Stop asking about this passage" onClick={() => assistant.clearFocus()}><X aria-hidden="true" /></button></p>}
      {chat.error && <Notice tone="error" action={settings || undefined}>{chat.error}</Notice>}
      <textarea autoComplete="off" aria-label="Message to the Sidebar Assistant" placeholder="Ask about the story, or for a change" rows={3} maxLength={8000}
        value={message} disabled={chat.busy} onChange={(event) => setMessage(event.target.value)} onKeyDown={keyDown} />
      <div className="sidecar-send">
        <span className="subtle keyboard-hint">Ctrl+Enter sends</span>
        <button type="submit" className="send-button" aria-label="Send to the Sidebar Assistant" disabled={chat.busy || !message.trim()}><ArrowUp aria-hidden="true" /></button>
      </div>
      <AiFooter />
    </form>
  )
}

function Welcome() {
  return (
    <div className="sidecar-welcome">
      <p>Ask about the story: &ldquo;what does Pell want?&rdquo;, &ldquo;make the last passage tenser&rdquo;, &ldquo;keep the next scenes quiet&rdquo;.</p>
      <p className="subtle">It can see the scene, the recent story, the people met, the journal, the lore and the author&rsquo;s note, and with the GM view on, what is behind the story. You review every change it proposes before it is used.</p>
    </div>
  )
}

interface CardProps { proposal: Proposal; onApply: () => void; onDismiss: () => void; onUndo: () => void }

function ProposalCard({ proposal, onApply, onDismiss, onUndo }: CardProps) {
  const { change } = proposal
  const label = title(change)
  const state = { pending: 'Proposed', working: 'Working…', applied: 'Done', dismissed: 'Dismissed' }[proposal.status]
  return (
    <section className={`sidecar-proposal ${proposal.status}`} aria-label={label}>
      <p className="eyebrow">{state}{GM_KINDS.includes(change.kind) && ' · GM'}</p>
      <strong>{label}</strong>
      <p className="subtle">{effect(change)}</p>
      <ProposalBody proposal={proposal} />
      {proposal.error && <p className="field-help-error" role="alert">{proposal.error}</p>}
      <div className="sidecar-actions">
        {proposal.status === 'pending' && <>
          <button type="button" className="button primary" onClick={onApply}>Apply</button>
          <button type="button" className="text-button" onClick={onDismiss}>Dismiss</button>
        </>}
        {proposal.status === 'applied' && <button type="button" className="text-button" onClick={onUndo}><Undo2 aria-hidden="true" />Undo</button>}
      </div>
    </section>
  )
}

function ProposalBody({ proposal }: { proposal: Proposal }): ReactNode {
  const { change } = proposal
  if (comparable(change)) {
    return <details><summary>Compare</summary>
      <p className="eyebrow">Before</p><p className="sidecar-value">{before(change)}</p>
      <p className="eyebrow">After</p><p className="sidecar-value">{after(change)}</p>
    </details>
  }
  return <p className="sidecar-value">{after(change)}</p>
}
