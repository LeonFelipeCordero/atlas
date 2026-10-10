import { hideTestFiles } from './graph-visibility'
import type { CircularDependency } from './architecture-artifact'
import type { CycleStructure, GraphStructure } from './graph-data'
import type { GraphNode, GraphScope, ProjectGraph } from './project-graph'

export type ProjectedCycle = {
  group: CircularDependency
  nodeIds: Array<string>
  edges: Array<{ id: string; source: string; target: string }>
  outsideCount: number
  scope: GraphScope
}

/** File ownership only, never evidence that a callable participates in imports. */
export function owningFile(
  artifact: Pick<GraphStructure, 'nodes'>,
  key: string,
): string | undefined {
  const lookup = new Map(artifact.nodes.map((node) => [node.stableKey, node]))
  const node = lookup.get(key)
  return [key, ...[...(node?.ancestorStableKeys ?? [])].reverse()].find(
    (id) => lookup.get(id)?.type === 'file',
  )
}

export function cycleContainsNode(
  artifact: Pick<GraphStructure, 'nodes'>,
  cycle: CircularDependency,
  node: GraphNode,
): boolean {
  if (node.kind !== 'folder')
    return cycle.nodeStableKeys.includes(owningFile(artifact, node.id) ?? '')
  return artifact.nodes.some(
    (member) =>
      cycle.nodeStableKeys.includes(member.stableKey) &&
      member.ancestorStableKeys.includes(node.id),
  )
}

export function containingCycleScope(
  artifact: Pick<GraphStructure, 'nodes'>,
  group: CircularDependency,
): GraphScope {
  const members = group.nodeStableKeys.map((key) =>
    artifact.nodes.find((node) => node.stableKey === key)!,
  )
  const common = [...members[0].ancestorStableKeys]
    .reverse()
    .find(
      (key) =>
        members.every((node) => node.ancestorStableKeys.includes(key)) &&
        artifact.nodes.some(
          (node) =>
            node.stableKey === key &&
            ['directory', 'folder'].includes(node.kind) &&
            node.path !== '.' &&
            node.path !== '',
        ),
    )
  return common ? { kind: 'folder', key: common } : { kind: 'repository' }
}

/** Project exported groups only. A hidden member removes the whole group, not a subcycle. */
export function projectCycles(
  artifact: CycleStructure,
  graph: ProjectGraph,
  scope: GraphScope,
): Array<ProjectedCycle> | undefined {
  if (!artifact.circularDependencies) return undefined
  const visible = new Set(
    hideTestFiles(artifact).nodes.map((node) => node.stableKey),
  )
  const lookup = new Map(artifact.nodes.map((node) => [node.stableKey, node]))
  return artifact.circularDependencies.groups
    .filter((group) => group.nodeStableKeys.every((key) => visible.has(key)))
    .map((group) => {
      const projection = new Map<string, string>()
      for (const key of group.nodeStableKeys) {
        const member = lookup.get(key)!
        const representative =
          graph.nodes.find((node) => node.id === key) ??
          graph.nodes.find(
            (node) =>
              node.kind === 'folder' &&
              member.ancestorStableKeys.includes(node.id),
          )
        if (representative) projection.set(key, representative.id)
      }
      const edges = new Map<
        string,
        { id: string; source: string; target: string }
      >()
      for (const edge of group.edges) {
        const source = projection.get(edge.sourceStableKey)
        const target = projection.get(edge.targetStableKey)
        if (
          !source ||
          !target ||
          (source === target && edge.sourceStableKey !== edge.targetStableKey)
        )
          continue
        const id = JSON.stringify([source, target])
        edges.set(id, { id, source, target })
      }
      const outsideCount = group.nodeStableKeys.filter(
        (key) =>
          scope.kind !== 'repository' &&
          key !== scope.key &&
          !lookup.get(key)!.ancestorStableKeys.includes(scope.key),
      ).length
      return {
        group,
        nodeIds: [...new Set(projection.values())],
        edges: [...edges.values()],
        outsideCount,
        scope: containingCycleScope(artifact, group),
      }
    })
    .filter(
      (cycle) =>
        cycle.nodeIds.length > 0 ||
        cycle.outsideCount < cycle.group.nodeStableKeys.length ||
        graph.nodes.some(
          (node) =>
            node.kind === 'function' &&
            cycleContainsNode(artifact, cycle.group, node),
        ),
    )
}
