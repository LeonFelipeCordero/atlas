import { expect, test } from 'bun:test'
import { buildProjectGraph } from './project-graph'
import type { Artifact, ArtifactNode } from './architecture-artifact'

function fixture(): Artifact {
  const nodes: Array<ArtifactNode> = []
  const add = (key: string, level: string, parent: string | null) => {
    const owner = nodes.find((node) => node.stableKey === parent)
    nodes.push({
      stableKey: key,
      name: key,
      path: key,
      type: level,
      kind: level === 'module' ? 'directory' : level,
      level,
      language: null,
      parentStableKey: parent,
      ancestorStableKeys: owner
        ? [...owner.ancestorStableKeys, owner.stableKey]
        : [],
      depth: owner ? owner.depth + 1 : 0,
    })
  }
  add('repo', 'repository', null)
  add('src', 'module', 'repo')
  add('current', 'module', 'src')
  add('local-file', 'file', 'current')
  add('local-type', 'type', 'local-file')
  add('local-call', 'callable', 'local-type')
  add('local-symbol', 'symbol', 'local-call')
  add('hidden', 'symbol', 'current')
  add('sibling', 'module', 'src')
  add('chain', 'module', 'sibling')
  add('target-file', 'file', 'chain')
  add('target-type', 'type', 'target-file')
  add('target-call', 'callable', 'target-type')
  add('nested-call', 'callable', 'target-call')
  add('target-symbol', 'symbol', 'nested-call')
  add('incoming', 'file', 'src')
  add('other', 'module', 'repo')
  add('other-file', 'file', 'other')
  add('external:a', 'external', 'repo')
  add('external:b', 'external', 'repo')
  return { schemaVersion: 2, repository: { name: 'test' }, nodes, edges: [] }
}

type BoundaryLink = {
  artifact: Artifact
  source: string
  target: string
  type?: string
}

function link({ artifact, source, target, type = 'CALLS' }: BoundaryLink) {
  artifact.edges.push({
    sourceStableKey: source,
    targetStableKey: target,
    type,
    confidence: 'EXTRACTED',
  })
}

const ids = (graph: ReturnType<typeof buildProjectGraph>) =>
  graph.nodes.map((node) => node.id).sort()

test('folder boundaries group below the LCA, compact, deduplicate and aggregate', () => {
  const artifact = fixture()
  link({ artifact, source: 'local-call', target: 'target-call' })
  link({ artifact, source: 'local-symbol', target: 'target-symbol' })
  link({
    artifact,
    source: 'local-file',
    target: 'target-file',
    type: 'IMPORTS',
  })
  link({ artifact, source: 'local-call', target: 'other-file' })
  link({ artifact, source: 'local-call', target: 'external:a' })
  link({
    artifact,
    source: 'local-call',
    target: 'external:a',
    type: '__proto__',
  })
  link({ artifact, source: 'local-call', target: 'hidden' })
  link({ artifact, source: 'local-call', target: 'local-symbol' })
  link({ artifact, source: 'incoming', target: 'local-call' })
  link({ artifact, source: 'target-call', target: 'external:b' })
  link({ artifact, source: 'external:a', target: 'external:b' })
  link({ artifact, source: 'hidden', target: 'incoming' })
  link({ artifact, source: 'local-call', target: 'incoming', type: 'CONTAINS' })
  const before = structuredClone(artifact)
  const graph = buildProjectGraph(artifact, { kind: 'folder', key: 'current' })
  expect(ids(graph)).toEqual(['chain', 'local-file', 'other'])
  expect(graph.nodes.find((node) => node.id === 'chain')).toMatchObject({
    role: 'boundary',
    kind: 'folder',
    label: 'sibling/chain',
    scope: { kind: 'folder', key: 'chain' },
  })
  expect(graph.edges.find((edge) => edge.target === 'chain')).toMatchObject({
    source: 'local-file',
    count: 3,
    relationships: { CALLS: 2, IMPORTS: 1 },
  })
  expect(graph.edges.some((edge) => edge.target === 'external:a')).toBe(false)
  expect(graph.edges).toHaveLength(2)
  expect(graph.edges.every((edge) => edge.source === 'local-file')).toBe(true)
  expect(artifact).toEqual(before)
})

test('file boundaries use nearest callable or file, keep folders and expose callable destinations', () => {
  const artifact = fixture()
  link({ artifact, source: 'local-call', target: 'target-symbol' })
  link({ artifact, source: 'local-symbol', target: 'nested-call' })
  link({ artifact, source: 'local-call', target: 'target-type', type: 'USES' })
  link({ artifact, source: 'local-call', target: 'sibling', type: 'USES' })
  link({ artifact, source: 'local-call', target: 'local-type' })
  link({ artifact, source: 'local-type', target: 'incoming' })
  link({ artifact, source: 'nested-call', target: 'other-file' })
  link({ artifact, source: 'nested-call', target: 'local-call' })
  const graph = buildProjectGraph(artifact, { kind: 'file', key: 'local-file' })
  expect(ids(graph)).toEqual([
    'chain',
    'local-call',
    'nested-call',
    'target-file',
  ])
  expect(graph.nodes.find((node) => node.id === 'nested-call')).toMatchObject({
    kind: 'function',
    role: 'boundary',
    scope: null,
    destination: {
      scope: { kind: 'file', key: 'target-file' },
      focusId: 'nested-call',
    },
  })
  expect(graph.nodes.find((node) => node.id === 'target-file')).toMatchObject({
    kind: 'file',
    role: 'boundary',
    scope: { kind: 'file', key: 'target-file' },
  })
  expect(graph.edges.find((edge) => edge.target === 'nested-call')?.count).toBe(
    2,
  )
  expect(graph.edges).toHaveLength(3)
})

function addExternalChild(artifact: Artifact) {
  const parent = artifact.nodes.find((node) => node.stableKey === 'external:a')!
  artifact.nodes.push({
    ...parent,
    stableKey: 'external:child',
    type: 'file',
    level: 'file',
    parentStableKey: parent.stableKey,
    ancestorStableKeys: [...parent.ancestorStableKeys, parent.stableKey],
    depth: parent.depth + 1,
  })
  link({ artifact, source: 'local-call', target: 'external:child' })
}

test('outside-scope test targets are excluded even with an unfiltered artifact', () => {
  const artifact = fixture()
  const file = artifact.nodes.find((node) => node.stableKey === 'target-file')!
  file.path = 'src/helper.test.ts'
  link({ artifact, source: 'local-call', target: 'target-call' })
  link({
    artifact,
    source: 'local-call',
    target: 'target-file',
    type: 'IMPORTS',
  })
  link({ artifact, source: 'local-call', target: 'other-file' })
  for (const scope of [
    { kind: 'folder', key: 'current' },
    { kind: 'file', key: 'local-file' },
  ] as const) {
    const graph = buildProjectGraph(artifact, scope)
    expect(
      graph.nodes
        .filter((node) => node.role === 'boundary')
        .map((node) => node.id),
    ).toEqual([scope.kind === 'file' ? 'other-file' : 'other'])
    expect(graph.edges).toHaveLength(1)
  }
  file.path = 'src/helper.ts'
  artifact.nodes.find((node) => node.stableKey === 'sibling')!.path =
    'src/__tests__'
  expect(
    buildProjectGraph(artifact, { kind: 'file', key: 'local-file' }).edges,
  ).toHaveLength(1)
})

test('outside-repository dependencies never appear at any scope', () => {
  const artifact = fixture()
  const a = artifact.nodes.find((node) => node.stableKey === 'external:a')!
  a.name = ''
  a.qualifiedName = 'package.a'
  artifact.nodes.find((node) => node.stableKey === 'external:b')!.name = ''
  link({ artifact, source: 'local-call', target: 'external:a' })
  link({
    artifact,
    source: 'local-file',
    target: 'external:a',
    type: 'IMPORTS',
  })
  link({ artifact, source: 'local-call', target: 'external:b' })
  link({ artifact, source: 'external:a', target: 'other-file' })
  link({ artifact, source: 'external:a', target: 'local-call' })
  addExternalChild(artifact)
  for (const scope of [
    { kind: 'repository' },
    { kind: 'folder', key: 'current' },
    { kind: 'file', key: 'local-file' },
  ] as const) {
    const graph = buildProjectGraph(artifact, scope)
    expect(graph.nodes.some((node) => node.id.startsWith('external:'))).toBe(
      false,
    )
    expect(graph.edges).toHaveLength(0)
  }
})
