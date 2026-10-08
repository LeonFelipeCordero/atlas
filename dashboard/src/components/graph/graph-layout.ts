import dagre from '@dagrejs/dagre'
import type { ProjectGraph } from '@/lib/project-graph'

export function layoutGraph(graph: ProjectGraph) {
  const connected = new Set(
    graph.edges.flatMap((edge) => [edge.source, edge.target]),
  )
  const layout = new dagre.graphlib.Graph()
    .setGraph({
      rankdir: 'LR',
      nodesep: 30,
      ranksep: 100,
      marginx: 30,
      marginy: 30,
    })
    .setDefaultEdgeLabel(() => ({}))
  for (const node of graph.nodes) {
    if (connected.has(node.id))
      layout.setNode(node.id, { width: 220, height: 78 })
  }
  for (const edge of graph.edges) layout.setEdge(edge.source, edge.target)
  dagre.layout(layout)
  const positions = new Map<string, { x: number; y: number }>()
  for (const id of connected) {
    const node = layout.node(id)
    positions.set(id, { x: node.x - 110, y: node.y - 39 })
  }
  const bottom = Math.max(
    0,
    ...Array.from(positions.values(), (position) => position.y + 128),
  )
  const isolated = graph.nodes.filter((node) => !connected.has(node.id))
  const columns = Math.max(2, Math.ceil(Math.sqrt(isolated.length)))
  isolated.forEach((node, index) =>
    positions.set(node.id, {
      x: (index % columns) * 260 + 30,
      y: bottom + Math.floor(index / columns) * 113 + 30,
    }),
  )
  return positions
}
