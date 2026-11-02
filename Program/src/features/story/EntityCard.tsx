import { useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { X } from 'lucide-react'
import { api } from '../../api'
import type { Gear, Journal, Story } from '../../types'
import { cardOf, namesIn, type Card, type CardAction, type EntityRef } from './entity'
import { EntityContext } from './entityContext'

/** A name that opens its card; plain text where there is no card to open. */
export function EntityName({ entity, children }: { entity: EntityRef; children: ReactNode }) {
  const entities = useContext(EntityContext)
  if (!entities) return <>{children}</>
  return <button type="button" className="entity-link" onClick={() => entities.open(entity)}>{children}</button>
}

interface HostProps { story: Story; onDraft: (text: string) => void; onFind: (key: string) => void; children: ReactNode }

/** Keeps the one card open at a time for the story screen, and the names its prose links. */
export function EntityHost({ story, onDraft, onFind, children }: HostProps) {
  const [entity, setEntity] = useState<EntityRef | null>(null)
  const value = { open: setEntity, links: namesIn(story) }
  const act = (action: CardAction) => {
    setEntity(null)
    if (action.find) onFind(action.find)
    else if (action.line) onDraft(action.line)
  }
  return <EntityContext.Provider value={value}>
    {children}
    {entity && <EntityCard entity={entity} story={story} onAct={act} onClose={() => setEntity(null)} />}
  </EntityContext.Provider>
}

/** The card's title and kind, beside the emblem or icon when the thing has one. */
function CardHead({ card, onClose }: { card: Card | null; onClose: () => void }) {
  return (
    <div className="entity-card-head">
      {card?.picture && <img className="entity-picture" src={card.picture} alt="" width={72} height={72} />}
      <div>
        <h2 id="entity-title">{card?.title ?? 'Gone'}</h2>
        {card && <p className="subtle">{card.kind}</p>}
      </div>
      <button type="button" className="icon-button" aria-label="Close" onClick={onClose}><X aria-hidden="true" /></button>
    </div>
  )
}

interface CardProps { entity: EntityRef; story: Story; onAct: (action: CardAction) => void; onClose: () => void }

/** The entity card (rule 2): what the character has seen of it and knows about it, and what they can do, each action
 *  a line for the composer. */
function EntityCard({ entity, story, onAct, onClose }: CardProps) {
  const dialog = useRef<HTMLDialogElement>(null)
  const gear = useQuery({ queryKey: ['story-gear'], queryFn: () => api<Gear>('/story/gear') })
  const journal = useQuery({ queryKey: ['story-journal'], queryFn: () => api<Journal>('/story/journal') })
  useEffect(() => {
    const element = dialog.current
    const opener = document.activeElement as HTMLElement | null
    element?.showModal?.()
    return () => { element?.close?.(); if (opener?.isConnected) opener.focus({ preventScroll: true }) }
  }, [])
  const card = cardOf(entity, story, gear.data, journal.data?.entries ?? [])
  return (
    <dialog ref={dialog} className="dialog entity-card" aria-labelledby="entity-title" onClose={onClose} onCancel={onClose}
      onClick={(event) => { if (event.target === dialog.current) onClose() }}>
      <CardHead card={card} onClose={onClose} />
      {card ? <div className="dialog-body">
        {card.about.map((line, index) => <p key={index}>{line}</p>)}
        {!!card.known.length && <>
          <h3 className="story-panel-heading">What you know</h3>
          <ul className="entity-known">{card.known.map((line, index) => <li key={index}>{line}</li>)}</ul>
        </>}
        {!!card.actions.length && <div className="form-actions entity-actions">
          {card.actions.map((action) => <button key={action.label} type="button" className="button" onClick={() => onAct(action)}
            title={action.line ? `Writes “${action.line}” for you to send` : undefined}>{action.label}</button>)}
        </div>}
      </div> : <p className="subtle">That is no longer in the story.</p>}
    </dialog>
  )
}
