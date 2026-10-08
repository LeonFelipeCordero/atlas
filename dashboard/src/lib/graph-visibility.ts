import { isTestPath } from './graph-test-path'
import { pushChildren } from './graph-traversal'
import type { Artifact, ArtifactNode } from './architecture-artifact'

export { isTestPath } from './graph-test-path'

const isFolder = (node: ArtifactNode) =>
  node.kind === 'directory' || node.kind === 'folder'

function isTestNode(node: ArtifactNode): boolean {
  if (!isFolder(node) && node.level !== 'file') return false
  return Boolean(node.path && isTestPath(node.path, isFolder(node)))
}

function hideEmptyFolder(
  node: ArtifactNode,
  nested: Array<ArtifactNode>,
  hidden: Set<string>,
) {
  if (
    isFolder(node) &&
    nested.length &&
    nested.every((child) => hidden.has(child.stableKey))
  )
    hidden.add(node.stableKey)
}

/** Derive a display artifact; never modify the imported snapshot. */
export function hideTestFiles(artifact: Artifact): Artifact {
  const children = new Map<string | null, Array<ArtifactNode>>()
  for (const node of artifact.nodes) {
    const siblings = children.get(node.parentStableKey) ?? []
    siblings.push(node)
    children.set(node.parentStableKey, siblings)
  }
  const hidden = new Set<string>()
  const ordered: Array<ArtifactNode> = []
  const stack = [...(children.get(null) ?? [])]
  while (stack.length) {
    const node = stack.pop()!
    ordered.push(node)
    pushChildren(stack, children.get(node.stableKey) ?? [])
    if (hidden.has(node.parentStableKey ?? '') || isTestNode(node))
      hidden.add(node.stableKey)
  }
  for (const node of ordered.reverse()) {
    const nested = children.get(node.stableKey) ?? []
    hideEmptyFolder(node, nested, hidden)
  }
  return {
    ...artifact,
    nodes: artifact.nodes.filter((node) => !hidden.has(node.stableKey)),
    edges: artifact.edges.filter(
      (edge) =>
        !hidden.has(edge.sourceStableKey) && !hidden.has(edge.targetStableKey),
    ),
  }
}
