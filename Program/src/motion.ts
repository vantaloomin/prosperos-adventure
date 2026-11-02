/** Whether to keep things still: the user's choice in Settings > Appearance, else the computer's setting
 * (the page root carries the choice, settings/useAppColors.ts). */
export function reducedMotion(): boolean {
  const chosen = document.documentElement.dataset.motion
  if (chosen === 'reduce') return true
  if (chosen === 'full') return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}
