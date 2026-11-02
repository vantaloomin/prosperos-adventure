import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api'
import type { Gear, Shop } from '../../types'
import { Notice } from '../../components/Feedback'
import { gearLine, haggleText, looksText, moneyText, slotsText } from './storyText'
import { EntityName } from './EntityCard'

const GEAR_KEY = ['story-gear']

/** The character's purse and pack (dungeon/inventory.py), and the shop window where the story is. */
export function StoryGear({ onTrade, open }: { onTrade: () => void; open?: boolean }) {
  const client = useQueryClient()
  const gear = useQuery({ queryKey: GEAR_KEY, queryFn: () => api<Gear>('/story/gear') })
  const [error, setError] = useState('')
  if (!gear.data) return null
  const trade = async (path: string, body: object) => {
    setError('')
    try { client.setQueryData(GEAR_KEY, await api<Gear>(path, body)); onTrade() }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'That did not go through.') }
  }
  const { coins, currency, items, shop, slots } = gear.data
  return (<>
    <details className="story-people" open={open}>
      <summary>Your pack ({moneyText(coins, currency)} · {slotsText(slots)})</summary>
      {gear.data.looks && <p className="subtle">How you look: {looksText(gear.data.looks)}</p>}
      <ul aria-label="Your pack">
        {items.map((item) => <li key={item.id}>
          <p className="story-thing"><ThingIcon src={item.icon} /><EntityName entity={{ kind: 'item', id: item.id }}>{gearLine(item)}</EntityName></p>
          {shop?.open && shop.offers[item.id] !== undefined && <div className="form-actions">
            <button type="button" className="text-button" onClick={() => void trade('/story/shop/sell', { inventory_id: item.id })}>
              Sell one for {moneyText(shop.offers[item.id], currency)}</button>
          </div>}
        </li>)}
      </ul>
    </details>
    {shop && <ShopWindow shop={shop} currency={currency} onBuy={(id) => void trade('/story/shop/buy', { item_id: id })} />}
    {error && <Notice tone="error">{error}</Notice>}
  </>)
}

/** A thing's picture beside its name (dungeon/icons.py); the name carries the meaning, so the picture is decoration. */
export function ThingIcon({ src }: { src?: string | null }) {
  return src ? <img className="story-thing-icon" src={src} alt="" width={32} height={32} loading="lazy" /> : null
}

function ShopWindow({ shop, currency, onBuy }: { shop: Shop; currency: Gear['currency']; onBuy: (itemId: string) => void }) {
  return (
    <details className="story-people" open>
      <summary>The counter{shop.open ? (shop.haggled ? ` (${haggleText(shop.haggled)})` : '') : ' (closed)'}</summary>
      {shop.open && <CounterNotes shop={shop} currency={currency} />}
      {shop.open ? <ul aria-label="For sale">
        {shop.stock.map((row) => <li key={row.item_id}>
          <p className="story-thing"><ThingIcon src={row.icon} /><span>{row.name} <span className="subtle">{moneyText(row.price, currency)} · {row.qty} left</span></span></p>
          <div className="form-actions">
            <button type="button" className="text-button" onClick={() => onBuy(row.item_id)}>Buy one</button>
          </div>
        </li>)}
      </ul> : <p className="subtle">Nobody is behind the counter. Come back in shop hours.</p>}
    </details>
  )
}

/** What to know at an open counter: how to trade, a fence, prices moved by events, the keeper's cash. */
function CounterNotes({ shop, currency }: { shop: Shop; currency: Gear['currency'] }) {
  return (<>
    <p className="subtle">Buy or sell here, or in the story (&ldquo;I buy two loaves&rdquo;, &ldquo;I sell the knife&rdquo;). Haggling is an Allure roll, once a day.</p>
    {shop.fence && <p className="subtle">The keeper fences stolen goods, and pays little for them.</p>}
    {shop.market && <p className="subtle">{shop.market}</p>}
    {shop.cash != null && <p className="subtle">The keeper has {moneyText(shop.cash, currency)} to buy with.</p>}
  </>)
}
