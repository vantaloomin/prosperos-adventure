/** Which ends of the world row have more worlds past them, so the fade and the arrow show only on that side. A few
 * pixels of slack keep a row scrolled to within rounding of its end from counting as more. */
export function rowEdges(left: number, width: number, total: number): { before: boolean; after: boolean } {
  return { before: left > 4, after: left + width < total - 4 }
}

/** The tile to move to from `index` with an arrow key, staying inside the row. */
export function nextTile(index: number, key: string, count: number): number {
  if (key === 'ArrowRight') return Math.min(index + 1, count - 1)
  if (key === 'ArrowLeft') return Math.max(index - 1, 0)
  if (key === 'Home') return 0
  if (key === 'End') return count - 1
  return index
}
