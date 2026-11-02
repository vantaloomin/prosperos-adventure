/** Keeps a typed number inside its range. While typing only the top is enforced, so "15" can be typed
 * through "1" when the least is 10; `leaving` (the box lost focus) enforces the bottom too. Blank stays blank. */
export function bounded(value: string, min?: number, max?: number, leaving = false): string {
  const number = Number(value)
  if (value.trim() === '' || !Number.isFinite(number)) return value
  if (max !== undefined && number > max) return String(max)
  if (leaving && min !== undefined && number < min) return String(min)
  return value
}

/** "1 event", "3 events"; `zero` stands in for 0 where it means none or automatic. */
export function countText(value: number, one: string, many: string, zero?: string): string {
  if (value === 0 && zero) return zero
  return `${value} ${value === 1 ? one : many}`
}

/** A span of hours in words: "6 hours", "1 day", "2 weeks". */
export function hoursText(hours: number): string {
  if (hours % 168 === 0) return countText(hours / 168, 'week', 'weeks')
  if (hours % 24 === 0) return countText(hours / 24, 'day', 'days')
  return countText(hours, 'hour', 'hours')
}

/** A span of minutes in words: "30 minutes", "2 hours", "1 day". */
export function minutesText(minutes: number): string {
  return minutes % 60 === 0 ? hoursText(minutes / 60) : countText(minutes, 'minute', 'minutes')
}

/** The presets as options, with a saved value that is not one of them kept at its sorted place. */
export function presetOptions(presets: number[], value: number, label: (value: number) => string): { value: number; label: string }[] {
  const values = presets.includes(value) ? presets : [...presets, value].sort((a, b) => a - b)
  return values.map(item => ({ value: item, label: label(item) }))
}
