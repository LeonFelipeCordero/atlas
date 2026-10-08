import { buildProjectGraph as buildFullGraph } from './project-graph'
import type { Artifact } from './architecture-artifact'
import type { GraphScope, ProjectGraph } from './project-graph'

// Local projection tests deliberately omit boundary nodes and their edges.
export function buildProjectGraph(
  artifact: Artifact,
  scope: GraphScope,
): ProjectGraph {
  const graph = buildFullGraph(artifact, scope)
  const nodes = graph.nodes.filter((node) => node.role !== 'boundary')
  const local = new Set(nodes.map((node) => node.id))
  return { nodes, edges: graph.edges.filter((edge) => local.has(edge.target)) }
}

export const ids = (graph: ProjectGraph) =>
  graph.nodes.map((node) => node.id).sort()
