import { expect } from 'bun:test'
import type { Artifact, ArtifactNode } from './architecture-artifact'
import type { GraphNode, GraphScope, ProjectGraph } from './project-graph'

function canAlias(artifact: Artifact, ancestor: ArtifactNode) {
  if (
    !['directory', 'folder'].includes(ancestor.kind) ||
    ['.', ''].includes(ancestor.path ?? '')
  )
    return false
  const children = artifact.nodes.filter(
    (child) =>
      child.parentStableKey === ancestor.stableKey &&
      child.level !== 'external' &&
      child.type !== 'external',
  )
  return (
    children.length === 1 && ['directory', 'folder'].includes(children[0].kind)
  )
}

type FolderAliasProjection = {
  artifact: Artifact
  node: GraphNode
  scope: GraphScope
  byKey: Map<string, ArtifactNode>
  aliases: Map<string, string>
}

function registerFolderAliases({
  artifact,
  node,
  scope,
  byKey,
  aliases,
}: FolderAliasProjection) {
  for (const key of [...byKey.get(node.id)!.ancestorStableKeys].reverse()) {
    if (scope.kind !== 'repository' && key === scope.key) break
    if (!canAlias(artifact, byKey.get(key)!)) break
    aliases.set(key, node.id)
  }
}

function projectAncestors(
  artifact: Artifact,
  aliases: Map<string, string>,
  byKey: Map<string, ArtifactNode>,
) {
  const projected = new Map<string, string>()
  for (const node of artifact.nodes) {
    const chain = [...node.ancestorStableKeys, node.stableKey].reverse()
    if (
      chain.some(
        (key) =>
          byKey.get(key)?.type === 'external' ||
          byKey.get(key)?.level === 'external',
      )
    )
      continue
    const group = chain.find((key) => aliases.has(key))
    if (group) projected.set(node.stableKey, aliases.get(group)!)
  }
  return projected
}

function expectedEdges(artifact: Artifact, projected: Map<string, string>) {
  const expected = new Map<
    string,
    { count: number; relationships: Record<string, number> }
  >()
  for (const edge of artifact.edges) {
    if (edge.type === 'CONTAINS') continue
    const source = projected.get(edge.sourceStableKey)
    const target = projected.get(edge.targetStableKey)
    if (!source || !target || source === target) continue
    const id = JSON.stringify([source, target])
    const entry = expected.get(id) ?? { count: 0, relationships: {} }
    entry.count++
    entry.relationships[edge.type] = (entry.relationships[edge.type] ?? 0) + 1
    expected.set(id, entry)
  }
  return expected
}

// Independent oracle uses validated ancestor arrays, not model traversal.
export function expectDirectProjection(
  artifact: Artifact,
  graph: ProjectGraph,
  scope: GraphScope = { kind: 'repository' },
) {
  const visible = new Set(graph.nodes.map((node) => node.id))
  const byKey = new Map(artifact.nodes.map((node) => [node.stableKey, node]))
  const aliases = new Map(graph.nodes.map((node) => [node.id, node.id]))
  for (const node of graph.nodes.filter((entry) => entry.kind === 'folder'))
    registerFolderAliases({ artifact, node, scope, byKey, aliases })
  const expected = expectedEdges(
    artifact,
    projectAncestors(artifact, aliases, byKey),
  )
  expect(graph.edges).toHaveLength(expected.size)
  expect(new Set(graph.edges.map((edge) => edge.id)).size).toBe(
    graph.edges.length,
  )
  for (const edge of graph.edges) {
    expect(visible.has(edge.source) && visible.has(edge.target)).toBe(true)
    expect(edge.source).not.toBe(edge.target)
    expect(edge.relationships.CONTAINS).toBeUndefined()
    expect({ count: edge.count, relationships: edge.relationships }).toEqual(
      expected.get(edge.id)!,
    )
  }
}

type ReachableNodes = {
  graph: ProjectGraph
  seenFiles: Set<string>
  seenFunctions: Set<string>
  pending: Array<GraphScope>
}

export function recordReachableNodes({
  graph,
  seenFiles,
  seenFunctions,
  pending,
}: ReachableNodes) {
  for (const node of graph.nodes) {
    if (node.kind === 'file') seenFiles.add(node.id)
    if (node.kind === 'function') seenFunctions.add(node.id)
    if (node.scope) pending.push(node.scope)
  }
}

export function expectNavigableTrail(
  artifact: Artifact,
  trail: Array<{ scope: GraphScope }>,
  build: (artifact: Artifact, scope: GraphScope) => ProjectGraph,
) {
  for (const crumb of trail)
    expect(() => build(artifact, crumb.scope)).not.toThrow()
}

export function enqueueFolders(
  graph: ProjectGraph,
  pending: Array<GraphScope>,
) {
  for (const node of graph.nodes)
    if (node.scope?.kind === 'folder') pending.push(node.scope)
}
