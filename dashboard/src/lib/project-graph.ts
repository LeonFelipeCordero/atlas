import { addBoundaryDependencies } from './project-graph-boundary'
import { pushChildren } from './graph-traversal'
import type { ArtifactNode } from './architecture-artifact'
import type { GraphHierarchy, GraphStructure } from './graph-data'
import type {
  GraphEdge,
  GraphNode,
  GraphScope,
  ProjectGraph,
} from './project-graph-types'

export type {
  GraphEdge,
  GraphNode,
  GraphScope,
  ProjectGraph,
} from './project-graph-types'

export class GraphScopeError extends Error {}

type Children = Map<string | null, Array<ArtifactNode>>
const isExternal = (node: ArtifactNode) =>
  node.level === 'external' || node.type === 'external'
const isFolder = (node: ArtifactNode) =>
  node.kind === 'directory' || node.kind === 'folder'
const isFile = (node: ArtifactNode) => node.level === 'file'

function indexChildren(artifact: GraphStructure): Children {
  const children: Children = new Map()
  for (const node of artifact.nodes) {
    const siblings = children.get(node.parentStableKey)
    if (siblings) siblings.push(node)
    else children.set(node.parentStableKey, [node])
  }
  return children
}

function* descendants(
  children: Children,
  parent: string | null,
): Generator<ArtifactNode> {
  const stack = [...(children.get(parent) ?? [])].reverse()
  while (stack.length) {
    const node = stack.pop()!
    if (isExternal(node)) continue
    yield node
    const nested = children.get(node.stableKey) ?? []
    pushChildren(stack, nested, true)
  }
}

const isTransparent = (node: ArtifactNode) =>
  node.level === 'repository' ||
  (isFolder(node) && (node.path === '.' || node.path === ''))

function rootNodes(children: Children): Array<ArtifactNode> {
  const visible: Array<ArtifactNode> = []
  const pending = [...(children.get(null) ?? [])]
  for (const node of pending) {
    if (isExternal(node)) continue
    // Repository and the exporter's synthetic '.' directory are transparent.
    if (isTransparent(node)) {
      pushChildren(pending, children.get(node.stableKey) ?? [])
      continue
    }
    if (isFolder(node) || isFile(node)) visible.push(node)
  }
  return visible
}

function scopeNode(artifact: Pick<GraphStructure, 'nodes'>, scope: GraphScope) {
  if (scope.kind === 'repository') return null
  if (!['folder', 'file'].includes(scope.kind))
    throw new GraphScopeError('Invalid graph scope')
  const parent = artifact.nodes.find((node) => node.stableKey === scope.key)
  const byKey = new Map(artifact.nodes.map((node) => [node.stableKey, node]))
  const external =
    parent &&
    [parent.stableKey, ...parent.ancestorStableKeys].some((key) => {
      const node = byKey.get(key)
      return node && isExternal(node)
    })
  if (!parent || external)
    throw new GraphScopeError(`Unknown graph scope: "${scope.key}"`)
  if (scope.kind === 'file' ? !isFile(parent) : !isFolder(parent))
    throw new GraphScopeError(
      `Invalid ${scope.kind} scope: "${scope.key}" must be a ${scope.kind}`,
    )
  return parent
}

function visibleNodes(
  artifact: GraphStructure,
  scope: GraphScope,
  children: Children,
) {
  const parent = scopeNode(artifact, scope)
  if (!parent) return rootNodes(children)
  if (scope.kind === 'folder')
    return (children.get(parent.stableKey) ?? []).filter(
      (node) => !isExternal(node) && (isFolder(node) || isFile(node)),
    )
  return Array.from(descendants(children, parent.stableKey)).filter(
    (node) => node.level === 'callable',
  )
}

function compactChain(
  node: ArtifactNode,
  children: Children,
): Array<ArtifactNode> {
  const chain = [node]
  while (isFolder(node)) {
    const nested = (children.get(node.stableKey) ?? []).filter(
      (child) => !isExternal(child),
    )
    if (nested.length !== 1 || !isFolder(nested[0])) break
    node = nested[0]
    chain.push(node)
  }
  return chain
}

const nodeLabel = (node: ArtifactNode) =>
  node.name || node.qualifiedName || node.stableKey

function sourceLines(node: ArtifactNode): string {
  if (node.startLine == null) return ''
  const end =
    node.endLine != null && node.endLine !== node.startLine
      ? `–${node.endLine}`
      : ''
  return `:${node.startLine}${end}`
}

function graphNode(node: ArtifactNode, children: Children): GraphNode {
  const id = node.stableKey
  const label = nodeLabel(node)
  const path = node.path ?? ''
  if (isFolder(node)) {
    const count = Array.from(descendants(children, id)).filter(isFile).length
    return {
      id,
      label,
      path,
      kind: 'folder',
      detail: `${count} ${count === 1 ? 'file' : 'files'}`,
      scope: { kind: 'folder', key: id },
    }
  }
  if (isFile(node)) {
    return {
      id,
      label,
      path,
      kind: 'file',
      detail: node.language ?? 'file',
      scope: { kind: 'file', key: id },
    }
  }
  const lines = sourceLines(node)
  return {
    id,
    label,
    path,
    kind: 'function',
    detail: `${node.kind} · ${path}${lines}`,
    scope: null,
    ...(node.properties ? { properties: node.properties } : {}),
  }
}

function projectNodes(children: Children, visible: Map<string, string>) {
  const projected = new Map<string, string>()
  // Parent-first traversal propagates the nearest visible ancestor in O(nodes).
  for (const node of descendants(children, null)) {
    const group =
      visible.get(node.stableKey) ?? projected.get(node.parentStableKey ?? '')
    if (group !== undefined) projected.set(node.stableKey, group)
  }
  return projected
}

function aggregateEdges(
  artifact: GraphStructure,
  projected: Map<string, string>,
  targets: Map<string, string>,
): Array<GraphEdge> {
  const edges = new Map<string, GraphEdge>()
  for (const direct of artifact.edges) {
    if (direct.type === 'CONTAINS') continue
    const source = projected.get(direct.sourceStableKey)
    const target = targets.get(direct.targetStableKey)
    if (source === undefined || target === undefined || source === target)
      continue
    const id = JSON.stringify([source, target])
    const edge = edges.get(id) ?? {
      id,
      source,
      target,
      count: 0,
      relationships: Object.create(null) as Record<string, number>,
    }
    edge.count++
    edge.relationships[direct.type] = (edge.relationships[direct.type] ?? 0) + 1
    edges.set(id, edge)
  }
  return Array.from(edges.values())
}

/**
 * Direct relations only; no precomputed views, caps, or artifact mutation.
 * Folders expose immediate children, compacting folder-only chains.
 * Files flatten classes, language modules and nested callables.
 * Original local sources expose one-hop outgoing boundaries, never incoming ones.
 * Unknown/mismatched scopes throw; valid empty scopes return an empty graph.
 */
export function buildProjectGraph(
  artifact: GraphStructure,
  scope: GraphScope,
): ProjectGraph {
  const children = indexChildren(artifact)
  const visible = new Map<string, string>()
  const render = (node: ArtifactNode, register = false) => {
    const chain = compactChain(node, children)
    const terminal = chain.at(-1)!
    if (register)
      for (const wrapper of chain)
        visible.set(wrapper.stableKey, terminal.stableKey)
    const result = graphNode(terminal, children)
    if (chain.length > 1)
      result.label = chain
        .map(
          (part) => part.path?.split('/').filter(Boolean).at(-1) || part.name,
        )
        .join('/')
    return result
  }
  const nodes = visibleNodes(artifact, scope, children).map((node) =>
    render(node, true),
  )
  const local = projectNodes(children, visible)
  const targets = addBoundaryDependencies(artifact, scope, local, nodes, render)
  return { nodes, edges: aggregateEdges(artifact, local, targets) }
}

/** Actual ancestors, including folders hidden by compaction. */
export function getGraphTrail(
  artifact: GraphHierarchy,
  scope: GraphScope,
): Array<{ label: string; scope: GraphScope }> {
  const node = scopeNode(artifact, scope)
  const trail: Array<{ label: string; scope: GraphScope }> = [
    { label: artifact.repository.name, scope: { kind: 'repository' } },
  ]
  if (!node) return trail
  const byKey = new Map(artifact.nodes.map((entry) => [entry.stableKey, entry]))
  for (const key of [...node.ancestorStableKeys, node.stableKey]) {
    const ancestor = byKey.get(key)!
    if (isTransparent(ancestor)) continue
    if (!isFolder(ancestor) && !isFile(ancestor)) continue
    trail.push({
      label: nodeLabel(ancestor),
      scope: { kind: isFolder(ancestor) ? 'folder' : 'file', key },
    })
  }
  return trail
}
