/** Shared graph record types. SQLite runtime responses are defined in graph-data.ts. */
export type NodeComplexity = {
  cyclomaticComplexity?: number
  baseCyclomaticComplexity?: number
  nestedCyclomaticComplexity?: number
  loopNestedComplexity?: number
  maxDecisionDepth?: number
}
export type NodeSizeMetrics = { lineCount?: number; parameterCount?: number }
export type NodeDependencyMetrics = {
  fanIn?: number
  fanOut?: number
  transitiveChangeImpact?: number
}
export type ArtifactNode = {
  stableKey: string
  type: string
  kind: string
  level: string
  name: string
  qualifiedName?: string | null
  path: string | null
  language: string | null
  parentStableKey: string | null
  ancestorStableKeys: Array<string>
  depth: number
  signature?: string | null
  startLine?: number | null
  startColumn?: number | null
  endLine?: number | null
  endColumn?: number | null
  properties?: Record<string, unknown> &
    NodeComplexity &
    NodeDependencyMetrics &
    NodeSizeMetrics
}
export type DirectEdge = {
  sourceStableKey: string
  targetStableKey: string
  type: string
  confidence: 'EXTRACTED' | 'INFERRED'
  path?: string | null
  line?: number | null
  evidence?: string | null
  typeOnly?: boolean
  sourceType?: string
  sourceKind?: string
  sourceLevel?: string
  targetType?: string
  targetKind?: string
  targetLevel?: string
}
export type CircularDependency = {
  id: string
  nodeStableKeys: Array<string>
  exampleCycle: Array<string>
  edges: Array<DirectEdge>
}

/** Exporter-shaped fixtures only; no runtime blob reader or parser. */
export type Artifact = {
  schemaVersion: 2
  repository: {
    name: string
    path?: string
    indexedAt?: string
    languages?: Array<string>
    [key: string]: unknown
  }
  nodes: Array<ArtifactNode>
  edges: Array<DirectEdge>
  circularDependencies?: { version: 1; groups: Array<CircularDependency> }
  views?: unknown
  stats?: unknown
  diagnostics?: Array<{
    severity: string
    path: string
    language: string
    message: string
  }>
  metadata?: unknown
  [key: string]: unknown
}
