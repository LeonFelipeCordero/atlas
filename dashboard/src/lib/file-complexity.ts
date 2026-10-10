import type { GraphStructure } from './graph-data'

export type FileComplexitySum = {
  total: number
  measured: number
  functions: number
}

/** Sum each owned function/method once, including class methods and nested functions. */
export function sumFileComplexity(
  artifact: Pick<GraphStructure, 'nodes'>,
  fileKey: string,
): FileComplexitySum {
  const summary = { total: 0, measured: 0, functions: 0 }
  const file = artifact.nodes.find((node) => node.stableKey === fileKey)
  if (file?.level !== 'file') return summary
  const fileKeys = new Set(
    artifact.nodes
      .filter((node) => node.level === 'file')
      .map((node) => node.stableKey),
  )
  for (const node of artifact.nodes) {
    if (!['function', 'method'].includes(node.type)) continue
    const owner = node.ancestorStableKeys
      .filter((key) => fileKeys.has(key))
      .at(-1)
    if (owner !== fileKey) continue
    summary.functions++
    const value = node.properties?.cyclomaticComplexity
    if (value === undefined) continue
    summary.total += value
    summary.measured++
  }
  return summary
}
