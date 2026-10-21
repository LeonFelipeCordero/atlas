import type {
  ArtifactNode,
  DirectEdge,
  NodeDependencyMetrics,
} from './architecture-artifact'

export type Adjacency = Map<string, Array<string>>

/** Stable key order uses Unicode code points, as in Python, not UTF-16 units. */
export function compareKeys(a: string, b: string): number {
  const left = Array.from(a)
  const right = Array.from(b)
  for (let index = 0; index < Math.min(left.length, right.length); index++) {
    const difference =
      left[index].codePointAt(0)! - right[index].codePointAt(0)!
    if (difference) return difference
  }
  return left.length - right.length
}

type FinishTraversal = {
  root: string
  adjacency: Adjacency
  visited: Set<string>
  finished: Array<string>
}

function finishFrom({ root, adjacency, visited, finished }: FinishTraversal) {
  const pending: Array<[string, number]> = [[root, 0]]
  while (pending.length) {
    const entry = pending[pending.length - 1]
    const targets = adjacency.get(entry[0])!
    if (entry[1] === targets.length) {
      finished.push(entry[0])
      pending.pop()
      continue
    }
    const target = targets[entry[1]++]
    if (visited.has(target)) continue
    visited.add(target)
    pending.push([target, 0])
  }
}

function finishOrder(adjacency: Adjacency): Array<string> {
  const visited = new Set<string>()
  const finished: Array<string> = []
  for (const root of adjacency.keys()) {
    if (visited.has(root)) continue
    visited.add(root)
    finishFrom({ root, adjacency, visited, finished })
  }
  return finished
}

function reverseGroup(root: string, reverse: Adjacency, visited: Set<string>) {
  const group: Array<string> = []
  const pending = [root]
  visited.add(root)
  while (pending.length) {
    const node = pending.pop()!
    group.push(node)
    for (const target of reverse.get(node)!) {
      if (visited.has(target)) continue
      visited.add(target)
      pending.push(target)
    }
  }
  return group.sort(compareKeys)
}

/** Iterative Kosaraju in source-first component order, matching the importer. */
export function components(adjacency: Adjacency): Array<Array<string>> {
  const reverse: Adjacency = new Map(
    [...adjacency.keys()].map((key) => [key, []]),
  )
  for (const [source, targets] of adjacency)
    for (const target of targets) reverse.get(target)!.push(source)
  const visited = new Set<string>()
  const groups: Array<Array<string>> = []
  for (const root of finishOrder(adjacency).reverse()) {
    if (visited.has(root)) continue
    groups.push(reverseGroup(root, reverse, visited))
  }
  return groups
}

export function levelOwners(nodes: Array<ArtifactNode>, level: string) {
  const lookup = new Map(nodes.map((node) => [node.stableKey, node]))
  return new Map(
    nodes.map((node) => [
      node.stableKey,
      [node.stableKey, ...[...node.ancestorStableKeys].reverse()].find(
        (key) => lookup.get(key)?.level === level,
      ),
    ]),
  )
}

function impactCounts(adjacency: Adjacency): Map<string, number> {
  const groups = components(adjacency)
  const membership = new Map(
    groups.flatMap((group, index) => group.map((key) => [key, index] as const)),
  )
  const pending = new Map<number, bigint>()
  const impact = new Map<string, number>()
  let offset = 0n
  groups.forEach((group, index) => {
    const bits =
      (pending.get(index) ?? 0n) |
      (((1n << BigInt(group.length)) - 1n) << offset)
    offset += BigInt(group.length)
    pending.delete(index)
    const count = bits.toString(2).replaceAll('0', '').length - 1
    for (const key of group) impact.set(key, count)
    const targets = new Set(
      group.flatMap((key) =>
        adjacency.get(key)!.map((target) => membership.get(target)!),
      ),
    )
    for (const target of targets)
      if (target !== index)
        pending.set(target, (pending.get(target) ?? 0n) | bits)
  })
  return impact
}

function levelAdjacency(
  nodes: Array<ArtifactNode>,
  edges: Array<Pick<DirectEdge, 'sourceStableKey' | 'targetStableKey'>>,
  level: string,
): Adjacency {
  const owners = levelOwners(nodes, level)
  const neighbors = new Map(
    nodes
      .filter((node) => node.level === level)
      .map((node) => [node.stableKey, new Set<string>()]),
  )
  for (const edge of edges) {
    const source = owners.get(edge.sourceStableKey)
    const target = owners.get(edge.targetStableKey)
    if (source && target && source !== target)
      neighbors.get(source)!.add(target)
  }
  return new Map(
    [...neighbors].map(([key, targets]) => [key, [...targets].sort()]),
  )
}

function addLevelMetrics(
  adjacency: Adjacency,
  metrics: Map<string, NodeDependencyMetrics>,
) {
  const impact = impactCounts(adjacency)
  const incoming = new Map<string, number>()
  for (const targets of adjacency.values())
    for (const target of targets)
      incoming.set(target, (incoming.get(target) ?? 0) + 1)
  for (const [key, targets] of adjacency) {
    const fanIn = incoming.get(key) ?? 0
    const fanOut = targets.length
    metrics.set(key, {
      fanIn,
      fanOut,
      instability: fanIn + fanOut === 0 ? null : fanOut / (fanIn + fanOut),
      transitiveChangeImpact: impact.get(key)!,
    })
  }
}

/** Exclude external roots and their entire subtrees using the full topology. */
export function internalNodes(nodes: Array<ArtifactNode>): Array<ArtifactNode> {
  const external = new Set(
    nodes
      .filter((node) => node.type === 'external' || node.level === 'external')
      .map((node) => node.stableKey),
  )
  return nodes.filter(
    (node) =>
      ![node.stableKey, ...node.ancestorStableKeys].some((key) =>
        external.has(key),
      ),
  )
}

/** Full internal topology, including hidden test dependents and type-only imports. */
export function dependencyMetrics(
  nodes: Array<ArtifactNode>,
  edges: Array<Pick<DirectEdge, 'sourceStableKey' | 'targetStableKey'>>,
): Map<string, NodeDependencyMetrics> {
  const metrics = new Map<string, NodeDependencyMetrics>()
  const internal = internalNodes(nodes)
  for (const level of ['module', 'file', 'type', 'callable'])
    addLevelMetrics(levelAdjacency(internal, edges, level), metrics)
  return metrics
}
