import { useState, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api'
import { Notice } from '../../components/Feedback'
import { InlineText } from '../../components/InlineText'
import { ROUND_KEY } from './useRound'
import { itemText, seatName, type RoundTable, type StatusLine, type TurnReport as Report } from './round'
import { checksLine, REPORT_NAMES, rollLine, turnName } from './roundText'

const STATUS_KEY = [...ROUND_KEY, 'status']

/** The status line under the round timeline between turns: the last turn played, which opens its report in place
 *  (docs/spec.md "Rolls, overrides and the turn report"). */
export function LastTurn({ table }: { table?: RoundTable }) {
  const status = useQuery({ queryKey: STATUS_KEY, queryFn: () => api<StatusLine>('/story/status-line') })
  const [open, setOpen] = useState(false)
  const last = status.data?.last
  if (!last) return null
  return (<>
    <button type="button" className="text-button round-last" aria-expanded={open} onClick={() => setOpen(!open)}>{turnName(last.number)}</button>
    {open && <TurnReport turnId={last.turn_id} table={table} />}
  </>)
}

export function TurnReport({ turnId, table }: { turnId: string; table?: RoundTable }) {
  const key = [...ROUND_KEY, 'report', turnId]
  const report = useQuery({ queryKey: key, queryFn: () => api<Report>(`/story/turns/${encodeURIComponent(turnId)}/report`) })
  const client = useQueryClient()
  const [error, setError] = useState('')
  if (report.isError) return <Notice tone="error">{report.error instanceof Error ? report.error.message : 'The report did not load'}</Notice>
  if (!report.data) return null
  const data = report.data
  const name = (key: string) => seatName(table, key)
  const strike = (invention: string) => api(`/story/turns/${encodeURIComponent(turnId)}/inventions/strike`, { name: invention })
    .then(() => Promise.all([client.invalidateQueries({ queryKey: key }), client.invalidateQueries({ queryKey: ['story'] })]),
      (failure: unknown) => setError(failure instanceof Error ? failure.message : 'Not struck'))
  const undo = (changeId: string) => api(`/story/turns/${encodeURIComponent(turnId)}/judged/${encodeURIComponent(changeId)}/undo`, {})
    .then(() => Promise.all([client.invalidateQueries({ queryKey: key }), client.invalidateQueries({ queryKey: ['story'] })]),
      (failure: unknown) => setError(failure instanceof Error ? failure.message : 'Not undone'))
  const you = [data.set.intent, ...data.set.lines.map((line) => `“${line}”`), ...data.set.beats].filter(Boolean)
  return (
    <div className="turn-report" aria-label={turnName(data.number)}>
      <Part title={REPORT_NAMES.you} items={you.map((text) => <InlineText text={text} />)} />
      <Part title={REPORT_NAMES.rolls} items={data.rolls.map((roll) => rollLine(roll, name))} />
      <Part title={REPORT_NAMES.motives} items={data.motives.map((item) => <>{name(item.seat)} · <InlineText text={item.motive} /></>)} />
      <Part title={REPORT_NAMES.numbers} items={data.numbers} />
      <Part title={REPORT_NAMES.inventions} items={data.inventions.filter((item) => item.name).map((item) => item.struck
        ? <s key={item.name}>{item.name}</s>
        : <span key={item.name}>{item.name} <button type="button" className="text-button" onClick={() => void strike(String(item.name))}>{REPORT_NAMES.strike}</button></span>)} />
      <Part title={REPORT_NAMES.judged} items={(data.judged ?? []).map((item) => item.undone
        ? <><s>{item.label}</s> · {REPORT_NAMES.undone}</>
        : <>{item.label} <button type="button" className="text-button" onClick={() => void undo(item.id)}>{REPORT_NAMES.undo}</button></>)} />
      <Part title={REPORT_NAMES.offpage} items={shown(data.offpage.map(itemText))} />
      <Part title={REPORT_NAMES.questions} items={shown(data.questions.map(itemText))} />
      <Part title={REPORT_NAMES.corrections} items={data.corrections.map((item) => item.why || item.target)} />
      <Part title={REPORT_NAMES.checks} items={[checksLine(data.checks)].filter(Boolean)} />
      <Part title={REPORT_NAMES.next} items={shown([data.next])} />
      {error && <Notice tone="error">{error}</Notice>}
    </div>
  )
}

/** Model lines with their Markdown styling, the empty ones left out. */
const shown = (lines: string[]) => lines.filter(Boolean).map((line) => <InlineText text={line} />)

/** One part of the report, only when it has anything in it. */
function Part({ title, items }: { title: string; items: ReactNode[] }) {
  if (!items.length) return null
  return (
    <section className="turn-report-part">
      <h3>{title}</h3>
      <ul>{items.map((item, index) => <li key={index}>{item}</li>)}</ul>
    </section>
  )
}
