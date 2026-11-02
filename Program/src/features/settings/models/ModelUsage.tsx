// The credits and usage rows on a profile card (usage.ts).
import { isLow, valueText, type Usage } from './usage'

export function ModelUsage({ usage }: { usage: Usage | null }) {
  if (!usage?.items.length) return null
  return <dl className="model-usage" aria-label="Credits and usage">
    {usage.plan && <div><dt>Plan</dt><dd>{usage.plan}</dd></div>}
    {usage.items.map(item => <div key={item.label}>
      <dt>{item.label}</dt>
      <dd className={isLow(item) ? 'low' : undefined}><span>{valueText(item)}</span>{item.percent_used !== undefined && <span className="usage-meter" aria-hidden="true"><span style={{ width: `${item.percent_used}%` }} /></span>}</dd>
    </div>)}
  </dl>
}
