import { isTestPath } from './graph-test-path'
import type {
  Artifact,
  ArtifactNode,
  DirectEdge,
} from './architecture-artifact'
import type { GraphNode, GraphScope } from './project-graph-types'

const isFolder = (node: ArtifactNode) =>
  ['directory', 'folder'].includes(node.kind)

function boundaryTarget(
  target: ArtifactNode,
  scope: GraphScope,
  byKey: Map<string, ArtifactNode>,
): ArtifactNode | undefined {
  const chain = [...target.ancestorStableKeys, target.stableKey]
  const ancestors = chain.map((key) => byKey.get(key)!)
  if (
    ancestors.some(
      (node) =>
        node.level === 'external' ||
        node.type === 'external' ||
        ((isFolder(node) || node.level === 'file') &&
          node.path &&
          isTestPath(node.path, isFolder(node))),
    )
  )
    return undefined
  if (scope.kind === 'repository' || chain.includes(scope.key)) return undefined
  if (scope.kind === 'file') {
    if (isFolder(target)) return target
    return (
      [...ancestors].reverse().find((node) => node.level === 'callable') ??
      [...ancestors].reverse().find((node) => node.level === 'file')
    )
  }
  const current = byKey.get(scope.key)!
  const currentChain = [...current.ancestorStableKeys, current.stableKey]
  let index = 0
  while (index < chain.length && chain[index] === currentChain[index]) index++
  return ancestors[index] ?? target
}

function renderBoundary(
  boundary: ArtifactNode,
  byKey: Map<string, ArtifactNode>,
  render: (node: ArtifactNode) => GraphNode,
): GraphNode {
  const result = render(boundary)
  result.role = 'boundary'
  if (boundary.level !== 'callable') return result
  const chain = [...boundary.ancestorStableKeys, boundary.stableKey].map(
    (key) => byKey.get(key)!,
  )
  const file = [...chain].reverse().find((node) => node.level === 'file')
  if (file)
    result.destination = {
      scope: { kind: 'file', key: file.stableKey },
      focusId: boundary.stableKey,
    }
  result.scope = null
  return result
}

function isBoundaryEdge(edge: DirectEdge, local: Map<string, string>) {
  return (
    edge.type !== 'CONTAINS' &&
    local.has(edge.sourceStableKey) &&
    !local.has(edge.targetStableKey)
  )
}

/** Only original local sources can introduce boundary targets. */
export function addBoundaryDependencies(
  artifact: Artifact,
  scope: GraphScope,
  local: Map<string, string>,
  nodes: Array<GraphNode>,
  render: (node: ArtifactNode) => GraphNode,
): Map<string, string> {
  const targets = new Map(local)
  const byKey = new Map(artifact.nodes.map((node) => [node.stableKey, node]))
  const visible = new Set(nodes.map((node) => node.id))
  const rendered = new Map<string, GraphNode>()
  for (const edge of artifact.edges) {
    if (!isBoundaryEdge(edge, local)) continue
    const target = byKey.get(edge.targetStableKey)
    if (!target) continue
    const boundary = boundaryTarget(target, scope, byKey)
    if (!boundary) continue
    const cached = rendered.get(boundary.stableKey)
    if (cached) {
      targets.set(edge.targetStableKey, cached.id)
      continue
    }
    const result = renderBoundary(boundary, byKey, render)
    rendered.set(boundary.stableKey, result)
    targets.set(edge.targetStableKey, result.id)
    if (visible.has(result.id)) continue
    visible.add(result.id)
    nodes.push(result)
  }
  return targets
}
