import { useId, useState } from 'react'
import type { WorkspaceSettings } from '../../types'
import { COLOR_SCHEMES, PALETTE_KEYS, defaultPalette, paletteReadability, paletteStyle, paperPalette, validHex, validPalette, type ColorScheme, type Palette } from './palette'

type Theme = NonNullable<WorkspaceSettings['theme']>
type Save = (change: { color_scheme?: ColorScheme; custom_palette?: Palette; theme?: Theme }) => Promise<void>
interface Props { theme: Theme; scheme: ColorScheme; palette: Palette | null; save: Save }

/** The swatch row: Match my computer (Paper or Ink, following the computer), the dark schemes, Paper and Custom. */
function choices(palette: Palette | null) {
  return [
    { id: 'system', label: 'Match my computer', className: 'swatch swatch-split', style: {}, change: { theme: 'system' as const } },
    ...COLOR_SCHEMES.map(option => ({ id: option.id, label: option.label, className: 'swatch', style: { background: option.swatch },
      change: { theme: 'scheme' as const, color_scheme: option.id } })),
    { id: 'paper', label: 'Paper', className: 'swatch swatch-light', style: { background: paperPalette.background }, change: { theme: 'paper' as const } },
    ...(palette ? [{ id: 'custom', label: 'Custom', className: 'swatch swatch-light', style: { background: palette.background },
      change: { theme: 'scheme' as const, color_scheme: 'custom' as const } }] : []),
  ]
}

/** General > Appearance: Prospero's Study's color schemes, Paper, Match my computer and a custom palette. Retro IM
 * keeps its own colors. Shared by every device on this workspace. */
export function ColorSchemeSettings({ theme, scheme, palette, save }: Props) {
  const name = useId()
  const chosen = theme === 'scheme' ? scheme : theme
  return (
    <div className="form-stack">
      <div>
        <h3>Colors</h3>
        <p className="subtle">The colors of the whole app. Retro IM keeps its own messenger colors.</p>
      </div>
      <fieldset className="palette-options">
        <legend className="visually-hidden">Color scheme</legend>
        {choices(palette).map((option) => (
          <label key={option.id} className="palette-option">
            <input type="radio" className="visually-hidden" name={name} value={option.id} checked={chosen === option.id} onChange={() => void save(option.change)} />
            <span className={option.className} style={option.style} aria-hidden="true" />{option.label}
          </label>
        ))}
      </fieldset>
      <CustomPalette saved={palette} apply={(custom) => save({ theme: 'scheme', color_scheme: 'custom', custom_palette: custom })} />
    </div>
  )
}

function CustomPalette({ saved, apply }: { saved: Palette | null; apply: (palette: Palette) => Promise<void> }) {
  const [draft, setDraft] = useState<Palette>(saved && validPalette(saved) ? saved : defaultPalette)
  const readability = paletteReadability(draft)
  const update = (key: keyof Palette, value: string) => setDraft({ ...draft, [key]: value })
  return (
    <details className="custom-palette">
      <summary>Custom palette</summary>
      <div className="form-stack">
        {PALETTE_KEYS.map((key) => <ColorControl key={key} name={key} value={draft[key]} onChange={(value) => update(key, value)} />)}
        <div className="palette-preview" style={paletteStyle(validPalette(draft) ? draft : defaultPalette)}>
          <p>There was still a little light at the end of the hall.</p>
          <button type="button" className="button primary">Sample action</button>
          <p className="subtle">Supporting text</p>
        </div>
        <p role="status" className="subtle">{validPalette(draft)
          ? `Text contrast ${readability.text.toFixed(2)}:1 (needs 4.5); accent contrast ${readability.accent.toFixed(2)}:1 (needs 3).${readability.valid ? '' : ' Adjust the colors before applying.'}`
          : 'Use six-digit hex colors, for example #c5a46d.'}</p>
        <div className="form-actions">
          <button type="button" className="button primary" disabled={!readability.valid} onClick={() => void apply({ ...draft })}>Apply custom palette</button>
          <button type="button" className="text-button" onClick={() => setDraft(defaultPalette)}>Start from Ink</button>
          <button type="button" className="text-button" onClick={() => setDraft(paperPalette)}>Start from Paper</button>
        </div>
      </div>
    </details>
  )
}

function ColorControl({ name, value, onChange }: { name: keyof Palette; value: string; onChange: (value: string) => void }) {
  const id = useId()
  const label = name[0].toUpperCase() + name.slice(1)
  return (
    <div className="color-control">
      <input type="color" aria-label={`${label} color`} value={validHex(value) ? value : defaultPalette[name]} onChange={(event) => onChange(event.target.value)} />
      <div className="field">
        <label htmlFor={id}>{label} hex</label>
        <input id={id} spellCheck={false} value={value} maxLength={7} aria-invalid={!validHex(value)} onChange={(event) => onChange(event.target.value)} />
      </div>
    </div>
  )
}
