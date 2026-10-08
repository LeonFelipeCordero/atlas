import type { ArtifactNode } from './architecture-artifact'

export type GraphScope =
  | { kind: 'repository' }
  | { kind: 'folder'; key: string }
  | { kind: 'file'; key: string }

export type GraphNode = {
  id: string
  label: string
  path: string
  kind: 'folder' | 'file' | 'function'
  role?: 'scope' | 'boundary'
  detail: string
  scope: GraphScope | null
  destination?: { scope: GraphScope; focusId: string }
  properties?: ArtifactNode['properties']
}

export type GraphEdge = {
  id: string
  source: string
  target: string
  count: number
  relationships: Record<string, number>
}

export type ProjectGraph = { nodes: Array<GraphNode>; edges: Array<GraphEdge> }
