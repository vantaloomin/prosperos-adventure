import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api, newId } from '../../api'
import type { View } from '../../workspace'
import { apply, undo } from './apply'
import { history, proposals, withProposal, type AssistantReply, type Proposal, type Turn } from './proposals'
import { assistant, useAssistant } from './store'

const turnsNow = () => assistant.get().turns
const update = (proposalId: string, change: Partial<Proposal>) => assistant.setTurns(withProposal(turnsNow(), proposalId, change))

/** Sending to the Sidebar Assistant, and applying or undoing what it proposes. */
export function useAssistantChat(view: View) {
  const { focus, turns } = useAssistant()
  const client = useQueryClient()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  /** Resolves true once the message was answered, so the composer can clear. */
  const send = async (text: string): Promise<boolean> => {
    setBusy(true)
    setError('')
    try {
      const result = await api<AssistantReply>('/assistant/chat', { message: text, history: history(turnsNow()), view, focus_message_id: focus?.id ?? null })
      assistant.setTurns([...turnsNow(), { id: newId(), message: text, reply: result.reply, proposals: proposals(result.changes, newId) }])
      assistant.clearFocus()
      return true
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'The assistant could not answer.')
      return false
    } finally { setBusy(false) }
  }
  const run = async (proposal: Proposal, action: 'apply' | 'undo') => {
    update(proposal.id, { status: 'working', error: undefined })
    try {
      if (action === 'apply') update(proposal.id, { status: 'applied', undo: await apply(proposal.change, client) })
      else { await undo(proposal, client); update(proposal.id, { status: 'pending', undo: undefined }) }
    } catch (failure) {
      update(proposal.id, { status: action === 'apply' ? 'pending' : 'applied', error: failure instanceof Error ? failure.message : 'That did not work.' })
    }
  }
  const applyAll = async (turn: Turn) => {
    for (const proposal of turn.proposals) if (proposal.status === 'pending') await run(proposal, 'apply')
  }
  return {
    turns, focus, busy, error, send, applyAll,
    apply: (proposal: Proposal) => void run(proposal, 'apply'),
    undo: (proposal: Proposal) => void run(proposal, 'undo'),
    dismiss: (proposal: Proposal) => update(proposal.id, { status: 'dismissed' }),
    clear: () => assistant.setTurns([]),
  }
}
export type AssistantChat = ReturnType<typeof useAssistantChat>
