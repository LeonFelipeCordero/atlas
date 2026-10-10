import type {
  ArtifactNode,
  CircularDependency,
  DirectEdge,
} from './architecture-artifact'
import type { FileComplexitySum } from './file-complexity'
import type { ProjectedCycle } from './graph-cycles'
import type { GraphScope, ProjectGraph } from './project-graph-types'

/** Navigation topology, not the exporter artifact (no views, stats, or opaque metadata). */
export type GraphStructure = {
  nodes: Array<ArtifactNode>
  edges: Array<DirectEdge>
}
export type GraphHierarchy = Pick<GraphStructure, 'nodes'> & {
  repository: { name: string }
}
export type CycleStructure = GraphStructure & {
  circularDependencies?: { version: 1; groups: Array<CircularDependency> }
}
export type GraphDiagnostic = {
  severity: string
  path: string
  language: string
  message: string
}
export type GraphDetails = {
  nodes: Array<ArtifactNode>
  fileComplexities: Record<string, FileComplexitySum>
}
export type ViewCycle = ProjectedCycle & {
  labels: Record<string, string>
  linkedNodeIds: Array<string>
}
export type GraphView = {
  state: 'ready'
  repositoryId: string
  importedAt: number
  graphRevision: string
  rootName: string
  scope: GraphScope
  graph: ProjectGraph
  relations: Array<DirectEdge>
  trail: Array<{ label: string; scope: GraphScope }>
  details: GraphDetails
  cycles: Array<ViewCycle>
  diagnostics: Array<GraphDiagnostic>
}
export type NeedsReindex = {
  state: 'needsReindex'
  repositoryId: string
  importedAt: number
  rootName: string
}
export type Architecture = GraphView | NeedsReindex
