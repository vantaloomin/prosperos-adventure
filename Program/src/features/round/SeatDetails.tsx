import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api'
import type { ModelsOverview } from '../settings/models/types'
import type { Seat, SeatEdit } from './round'
import { SEAT_NAMES } from './roundText'

/** In a thinking character's open row: the user's notes on them, which go into their own context, and the model they
 *  think with, over the agents' model (PUT /api/rounds/seats/{key}). */
export function SeatDetails({ seat, onSave }: { seat: Seat; onSave: (edit: SeatEdit) => void }) {
  const profiles = useQuery({ queryKey: ['models'], queryFn: () => api<ModelsOverview>('/models') }).data?.profiles ?? []
  const [notes, setNotes] = useState(seat.notes)
  const ready = profiles.filter((profile) => profile.ready)
  return (
    <div className="seat-details">
      <textarea aria-label={SEAT_NAMES.notes(seat.name)} placeholder={SEAT_NAMES.notesHint} rows={2} maxLength={600} value={notes}
        onChange={(event) => setNotes(event.target.value)} onBlur={() => { if (notes !== seat.notes) onSave({ notes }) }} />
      {ready.length > 0 && <select aria-label={SEAT_NAMES.model(seat.name)} value={seat.model_profile_id ?? ''} onChange={(event) => onSave({ model_profile_id: event.target.value })}>
        <option value="">{SEAT_NAMES.agentsModel}</option>
        {ready.map((profile) => <option key={profile.id} value={profile.id}>{profile.name}</option>)}
      </select>}
    </div>
  )
}
