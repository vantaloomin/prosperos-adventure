// Kept free of imports so tests/ui can load it directly.

/** Splits streamed newline-delimited JSON into whole lines and the unfinished rest. */
export function ndjsonLines(buffer: string): [unknown[], string] {
  const parts = buffer.split('\n')
  const rest = parts.pop() ?? ''
  return [parts.filter((line) => line.trim()).map((line) => JSON.parse(line) as unknown), rest]
}
