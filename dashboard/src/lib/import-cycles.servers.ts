import { createHash } from 'node:crypto'
import { compareKeys, components } from './graph-analysis'
import type { Adjacency } from './graph-analysis'
import type {
  ArtifactNode,
  CircularDependency,
  DirectEdge,
} from './architecture-artifact'

// Python's JSON defaults use ASCII escapes and a space after separators.
function pythonJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(pythonJson).join(', ')}]`
  if (value !== null && typeof value === 'object')
    return `{${Object.entries(value)
      .filter(([, entry]) => entry !== undefined)
      .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
      .map(([key, entry]) => `${pythonJson(key)}: ${pythonJson(entry)}`)
      .join(', ')}}`
  return JSON.stringify(value).replace(
    /[\u007f-\uffff]/g,
    (character) =>
      `\\u${character.charCodeAt(0).toString(16).padStart(4, '0')}`,
  )
}

function fileOwners(nodes: Array<ArtifactNode>) {
  const lookup = new Map(nodes.map((node) => [node.stableKey, node]))
  return new Map(
    nodes.map((node) => {
      const chain = [node.stableKey, ...[...node.ancestorStableKeys].reverse()]
      const boundary = chain.find((key) => {
        const member = lookup.get(key)!
        return (
          member.type === 'file' ||
          member.type === 'external' ||
          member.level === 'external'
        )
      })
      return [
        node.stableKey,
        boundary && lookup.get(boundary)?.type === 'file'
          ? boundary
          : undefined,
      ]
    }),
  )
}

function projectImport(
  edge: DirectEdge,
  owners: Map<string, string | undefined>,
): DirectEdge | null {
  if (edge.type !== 'IMPORTS' || edge.typeOnly) return null
  const source = owners.get(edge.sourceStableKey)
  const target = owners.get(edge.targetStableKey)
  if (!source || !target) return null
  if (
    source === target &&
    (edge.sourceStableKey !== source || edge.targetStableKey !== target)
  )
    return null
  const { path, line, evidence, confidence, type } = edge
  return {
    sourceStableKey: source,
    targetStableKey: target,
    path,
    line,
    evidence,
    confidence,
    type,
  }
}

function projectImports(nodes: Array<ArtifactNode>, edges: Array<DirectEdge>) {
  const owners = fileOwners(nodes)
  const projected: Array<DirectEdge> = []
  for (const edge of edges) {
    const projection = projectImport(edge, owners)
    if (projection) projected.push(projection)
  }
  const sortKey = (edge: DirectEdge) => pythonJson(edge)
  return projected.sort((a, b) =>
    sortKey(a) < sortKey(b) ? -1 : sortKey(a) > sortKey(b) ? 1 : 0,
  )
}

function cyclePath(start: string, parents: Map<string, string | null>) {
  const path = [start]
  let current = parents.get(start) ?? null
  while (current !== null) {
    path.push(current)
    current = parents.get(current) ?? null
  }
  return [start, ...path.reverse()]
}

type CycleSearch = {
  node: string
  targets: Array<string>
  members: Set<string>
  start: string
  parents: Map<string, string | null>
  pending: Array<string>
}

function cycleNeighbors({
  node,
  targets,
  members,
  start,
  parents,
  pending,
}: CycleSearch) {
  for (const target of targets) {
    if (!members.has(target) || parents.has(target)) continue
    parents.set(target, node)
    if (target === start) return true
    pending.push(target)
  }
  return false
}

function exampleCycle(
  group: Array<string>,
  adjacency: Adjacency,
): Array<string> {
  const start = group[0]
  if (group.length === 1) return [start, start]
  const members = new Set(group)
  const first = adjacency
    .get(start)!
    .find((key) => key !== start && members.has(key))!
  const parents = new Map<string, string | null>([[first, null]])
  const pending = [first]
  for (const node of pending)
    if (
      cycleNeighbors({
        node,
        targets: adjacency.get(node)!,
        members,
        start,
        parents,
        pending,
      })
    )
      return cyclePath(start, parents)
  throw new Error('Import component has no return path')
}

/** Normalized IMPORTS analysis; never consult the removed exporter blob. */
export function importCycles(
  nodes: Array<ArtifactNode>,
  edges: Array<DirectEdge>,
): Array<CircularDependency> {
  const projected = projectImports(nodes, edges)
  const neighbors = new Map<string, Set<string>>()
  for (const edge of projected) {
    if (!neighbors.has(edge.sourceStableKey))
      neighbors.set(edge.sourceStableKey, new Set())
    if (!neighbors.has(edge.targetStableKey))
      neighbors.set(edge.targetStableKey, new Set())
    neighbors.get(edge.sourceStableKey)!.add(edge.targetStableKey)
  }
  const adjacency: Adjacency = new Map(
    [...neighbors.keys()]
      .sort(compareKeys)
      .map((key) => [key, [...neighbors.get(key)!].sort(compareKeys)]),
  )
  const groups = components(adjacency)
    .filter(
      (group) =>
        group.length > 1 || adjacency.get(group[0])!.includes(group[0]),
    )
    .sort((a, b) => compareKeys(a.join('\0'), b.join('\0')))
  return groups.map((keys) => {
    const members = new Set(keys)
    return {
      id: `import-cycle:${createHash('sha256').update(pythonJson(keys)).digest('hex')}`,
      nodeStableKeys: keys,
      exampleCycle: exampleCycle(keys, adjacency),
      edges: projected.filter(
        (edge) =>
          members.has(edge.sourceStableKey) &&
          members.has(edge.targetStableKey),
      ),
    }
  })
}
