import type { GraphNode, ProjectGraph } from '@/lib/project-graph'

const compareNodes = (first: GraphNode, second: GraphNode) =>
  first.label.localeCompare(second.label) || first.id.localeCompare(second.id)

export function layoutGraph({ nodes, edges }: ProjectGraph) {
  const nodeIds = new Set(nodes.map((node) => node.id))
  const outgoing = new Map<string, Array<string>>()
  const incoming = new Set<string>()
  for (const edge of edges) {
    if (!nodeIds.has(edge.source) || !nodeIds.has(edge.target)) continue
    outgoing.set(edge.source, [
      ...(outgoing.get(edge.source) ?? []),
      edge.target,
    ])
    incoming.add(edge.target)
  }
  const sorted = [...nodes].sort(compareNodes)
  const roots = sorted.filter((node) => !incoming.has(node.id))
  const ranks = new Map(roots.map((node) => [node.id, 0]))
  const queue = roots.map((node) => node.id)
  const visit = (start: number) => {
    for (let index = start; index < queue.length; index += 1) {
      const source = queue[index]
      for (const target of outgoing.get(source) ?? []) {
        if (ranks.has(target)) continue
        ranks.set(target, ranks.get(source)! + 1)
        queue.push(target)
      }
    }
  }
  visit(0)
  for (const node of sorted) {
    if (ranks.has(node.id)) continue
    ranks.set(node.id, 0)
    queue.push(node.id)
    visit(queue.length - 1)
  }
  const columns = new Map<number, number>()
  return new Map(
    sorted.map((node) => {
      const rank = ranks.get(node.id)!
      const column = columns.get(rank) ?? 0
      columns.set(rank, column + 1)
      return [node.id, { x: 32 + column * 272, y: 32 + rank * 118 }]
    }),
  )
}
