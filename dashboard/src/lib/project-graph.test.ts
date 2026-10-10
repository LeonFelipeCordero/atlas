import { beforeAll, describe, expect, test } from 'bun:test'
import { getGraphTrail } from './project-graph'
import { buildProjectGraph, ids } from './project-graph-test.helpers'
import {
  expectDirectProjection,
  expectNavigableTrail,
  recordReachableNodes,
} from './project-graph-projection-test-helpers'
import { fixtureNodes } from './project-graph-fixture'
import { artifactFixtures, importedArtifact } from './imported-artifact-fixture'
import type { Artifact, DirectEdge } from './architecture-artifact'
import type { GraphScope, ProjectGraph } from './project-graph'

// This file must also prepare the CLI fixture when run independently.
beforeAll(() => {
  importedArtifact()
}, 30_000)

function fixture(): Artifact {
  const nodes = fixtureNodes()
  const edges: Array<DirectEdge> = nodes
    .filter((node) => node.parentStableKey !== null)
    .map((node) => ({
      sourceStableKey: node.parentStableKey!,
      targetStableKey: node.stableKey,
      type: 'CONTAINS',
      confidence: 'EXTRACTED',
    }))
  const link = (source: string, target: string, type = 'CALLS') =>
    edges.push({
      sourceStableKey: source,
      targetStableKey: target,
      type,
      confidence: 'EXTRACTED',
    })
  link('run', 'lib-fn')
  link('run', 'lib-fn')
  link('helper', 'lib-file', 'IMPORTS')
  link('lib-fn', 'run')
  link('run', 'other-fn')
  link('helper', 'other-file', 'IMPORTS')
  link('run', 'helper-fn')
  link('run', 'helper-fn')
  link('helper-fn', 'run')
  link('run', 'stop')
  link('run', 'stop')
  link('variable', 'stop', 'READS')
  link('nested', 'stop')
  link('stop', 'variable', 'WRITES')
  link('run', 'nested')
  link('run', 'run')
  link('Service', 'run', 'DECLARES')
  link('run', 'external')
  link('external', 'run')
  link('external-child', 'run')
  link('run', 'direct-fn')
  link('direct-fn', 'run')
  link('run', 'root-fn')
  link('root-fn', 'run')
  return {
    schemaVersion: 2,
    repository: { name: 'synthetic' },
    nodes,
    edges,
    views: { ignored: true },
  }
}

function tree(rows: Array<[string, string, string | null]>): Artifact {
  const artifact = fixture()
  artifact.nodes = []
  artifact.edges = []
  for (const [key, kind, parent] of rows) {
    const owner = artifact.nodes.find((node) => node.stableKey === parent)
    artifact.nodes.push({
      stableKey: key,
      name: key.split('/').at(-1)!,
      path: key,
      type: kind,
      kind,
      level: kind === 'folder' ? 'module' : kind,
      language: null,
      parentStableKey: parent,
      ancestorStableKeys: owner
        ? [...owner.ancestorStableKeys, owner.stableKey]
        : [],
      depth: owner ? owner.depth + 1 : 0,
    })
  }
  return artifact
}

const relation = (graph: ProjectGraph, source: string, target: string) =>
  graph.edges.find((edge) => edge.source === source && edge.target === target)

type ExpectedRelation = {
  graph: ProjectGraph
  source: string
  target: string
  relationships: Record<string, number>
}

function expectRelations({
  graph,
  source,
  target,
  relationships,
}: ExpectedRelation) {
  expect(relation(graph, source, target)).toEqual({
    id: JSON.stringify([source, target]),
    source,
    target,
    count: Object.values(relationships).reduce(
      (total, count) => total + count,
      0,
    ),
    relationships,
  })
}

describe('adaptive graph scopes', () => {
  test('root folders and files, with directed cross-module aggregation', () => {
    const graph = buildProjectGraph(fixture(), { kind: 'repository' })
    expect(ids(graph)).toEqual(['app', 'lib', 'root-file'])
    expect(graph.nodes.find((node) => node.id === 'app')?.scope).toEqual({
      kind: 'folder',
      key: 'app',
    })
    expect(graph.nodes.find((node) => node.id === 'root-file')?.scope).toEqual({
      kind: 'file',
      key: 'root-file',
    })
    expectRelations({
      graph,
      source: 'app',
      target: 'lib',
      relationships: { CALLS: 2, IMPORTS: 1 },
    })
    expectRelations({
      graph,
      source: 'lib',
      target: 'app',
      relationships: { CALLS: 1 },
    })
    expectRelations({
      graph,
      source: 'app',
      target: 'root-file',
      relationships: { CALLS: 1 },
    })
    expectRelations({
      graph,
      source: 'root-file',
      target: 'app',
      relationships: { CALLS: 1 },
    })
    expect(graph.edges).toHaveLength(4)
  })
  test('immediate packages alongside module direct files', () => {
    const graph = buildProjectGraph(fixture(), {
      kind: 'folder',
      key: 'app',
    })
    expect(ids(graph)).toEqual(['direct', 'empty', 'other', 'pkg'])
    expect(graph.nodes.find((node) => node.id === 'pkg')?.scope).toEqual({
      kind: 'folder',
      key: 'pkg',
    })
    expect(graph.nodes.find((node) => node.id === 'direct')?.scope).toEqual({
      kind: 'file',
      key: 'direct',
    })
    expectRelations({
      graph,
      source: 'pkg',
      target: 'other',
      relationships: { CALLS: 1, IMPORTS: 1 },
    })
    expectRelations({
      graph,
      source: 'pkg',
      target: 'direct',
      relationships: { CALLS: 1 },
    })
    expectRelations({
      graph,
      source: 'direct',
      target: 'pkg',
      relationships: { CALLS: 1 },
    })
    expect(graph.edges).toHaveLength(3)
  })
})

describe('adaptive graph scopes: compacted folders and files', () => {
  test('compacts deep folder chains without flattening files', () => {
    const artifact = fixture()
    const graph = buildProjectGraph(artifact, { kind: 'folder', key: 'pkg' })
    expect(ids(graph)).toEqual(['acme', 'helper'])
    expect(graph.nodes.find((node) => node.id === 'acme')).toMatchObject({
      label: 'java/com/acme',
      kind: 'folder',
      detail: '1 file',
      scope: { kind: 'folder', key: 'acme' },
    })
    expectRelations({
      graph,
      source: 'acme',
      target: 'helper',
      relationships: { CALLS: 2 },
    })
    expectRelations({
      graph,
      source: 'helper',
      target: 'acme',
      relationships: { CALLS: 1 },
    })
    expect(graph.edges).toHaveLength(2)
    expect(
      ids(buildProjectGraph(artifact, { kind: 'folder', key: 'acme' })),
    ).toEqual(['service'])
  })
  test('flattens class methods and nested callables; local symbols project to their callable', () => {
    const graph = buildProjectGraph(fixture(), {
      kind: 'file',
      key: 'service',
    })
    expect(ids(graph)).toEqual(['nested', 'run', 'stop'])
    expect(
      graph.nodes.every(
        (node) => node.kind === 'function' && node.scope === null,
      ),
    ).toBe(true)
    expect(graph.nodes.find((node) => node.id === 'run')).toEqual({
      id: 'run',
      label: 'run',
      path: 'app/pkg/java/com/acme/Service.java',
      kind: 'function',
      detail: 'method · app/pkg/java/com/acme/Service.java:10–20',
      scope: null,
    })
    expectRelations({
      graph,
      source: 'run',
      target: 'stop',
      relationships: { CALLS: 2, READS: 1 },
    })
    expectRelations({
      graph,
      source: 'nested',
      target: 'stop',
      relationships: { CALLS: 1 },
    })
    expectRelations({
      graph,
      source: 'stop',
      target: 'run',
      relationships: { WRITES: 1 },
    })
    expectRelations({
      graph,
      source: 'run',
      target: 'nested',
      relationships: { CALLS: 1 },
    })
    expect(graph.edges).toHaveLength(4)
  })
})

test('handles empty scopes and rejects unknown or mismatched scopes', () => {
  const artifact = fixture()
  expect(buildProjectGraph(artifact, { kind: 'folder', key: 'empty' })).toEqual(
    { nodes: [], edges: [] },
  )
  for (const scope of [
    { kind: 'folder', key: 'missing' },
    { kind: 'file', key: 'missing' },
    { kind: 'folder', key: 'service' },
    { kind: 'file', key: 'app' },
    { kind: 'file', key: 'external' },
  ] satisfies Array<GraphScope>) {
    expect(() => buildProjectGraph(artifact, scope)).toThrow('scope')
    expect(() => getGraphTrail(artifact, scope)).toThrow('scope')
  }
  expect(
    buildProjectGraph(
      { ...artifact, nodes: [], edges: [] },
      { kind: 'repository' },
    ),
  ).toEqual({ nodes: [], edges: [] })
})

test('structural edges alone never create relationships; precomputed views are irrelevant', () => {
  const artifact = fixture()
  artifact.edges = artifact.edges.filter((edge) => edge.type === 'CONTAINS')
  artifact.views = {
    module: {
      edges: [{ sourceStableKey: 'app', targetStableKey: 'lib', count: 999 }],
    },
  }
  for (const scope of [
    { kind: 'repository' },
    { kind: 'folder', key: 'app' },
    { kind: 'folder', key: 'pkg' },
    { kind: 'file', key: 'service' },
  ] satisfies Array<GraphScope>)
    expect(buildProjectGraph(artifact, scope).edges).toEqual([])
})

test('supports roots without synthetic wrappers and unsorted imports without mutation', () => {
  const artifact = fixture()
  artifact.nodes = artifact.nodes
    .filter((node) => !['repo', 'root'].includes(node.stableKey))
    .map((node) => ({
      ...node,
      parentStableKey: ['repo', 'root'].includes(node.parentStableKey ?? '')
        ? null
        : node.parentStableKey,
      ancestorStableKeys: node.ancestorStableKeys.filter(
        (key) => !['repo', 'root'].includes(key),
      ),
      depth: node.ancestorStableKeys.filter(
        (key) => !['repo', 'root'].includes(key),
      ).length,
    }))
    .reverse()
  const keys = new Set(artifact.nodes.map((node) => node.stableKey))
  artifact.edges = artifact.edges.filter(
    (edge) => keys.has(edge.sourceStableKey) && keys.has(edge.targetStableKey),
  )
  const before = structuredClone(artifact)
  const graph = buildProjectGraph(artifact, {
    kind: 'repository',
  })
  expect(ids(graph)).toEqual(['app', 'lib', 'root-file'])
  expectDirectProjection(artifact, graph)
  expect(artifact).toEqual(before)
  expect(buildProjectGraph(artifact, { kind: 'repository' })).toEqual(graph)
})

test('does not cap large graphs; aggregates prototype-like relationship names safely', () => {
  const artifact = fixture()
  const template = artifact.nodes.find(
    (node) => node.stableKey === 'root-file',
  )!
  for (let index = 0; index < 1500; index++)
    artifact.nodes.push({
      ...template,
      stableKey: `file:${index}`,
      name: `${index}.ts`,
    })
  artifact.edges.push({
    sourceStableKey: 'run',
    targetStableKey: 'lib-fn',
    type: '__proto__',
    confidence: 'INFERRED',
  })
  const graph = buildProjectGraph(artifact, {
    kind: 'repository',
  })
  expect(graph.nodes).toHaveLength(1503)
  expect(
    buildProjectGraph(artifact, { kind: 'folder', key: 'root' }).nodes,
  ).toHaveLength(1503)
  expect(relation(graph, 'app', 'lib')?.relationships.__proto__).toBe(1)
  expect(relation(graph, 'app', 'lib')?.count).toBe(4)
})

for (const [name, createArtifact] of Object.entries(artifactFixtures)) {
  test(`${name}: every file and callable is reachable with exact direct-edge counts`, () => {
    const artifact = createArtifact()
    const expected =
      name === 'CLI language samples'
        ? { nodes: 35, edges: 39, files: 7, callables: 12 }
        : { nodes: 2022, edges: 8421, files: 400, callables: 1600 }
    expect(artifact.nodes).toHaveLength(expected.nodes)
    expect(artifact.edges).toHaveLength(expected.edges)
    const pending: Array<GraphScope> = [{ kind: 'repository' }]
    const seenFiles = new Set<string>()
    const seenFunctions = new Set<string>()
    const levels = new Set<string>()
    for (const scope of pending) {
      const graph = buildProjectGraph(artifact, scope)
      levels.add(scope.kind)
      expectDirectProjection(artifact, graph, scope)
      expect(new Set(ids(graph)).size).toBe(graph.nodes.length)
      recordReachableNodes({ graph, seenFiles, seenFunctions, pending })
    }
    expect([...levels].sort()).toEqual(['file', 'folder', 'repository'])
    expect(seenFiles.size).toBe(expected.files)
    expect(seenFunctions.size).toBe(expected.callables)
    expect([...seenFiles].sort()).toEqual(
      artifact.nodes
        .filter((node) => node.level === 'file')
        .map((node) => node.stableKey)
        .sort(),
    )
    expect([...seenFunctions].sort()).toEqual(
      artifact.nodes
        .filter((node) => node.level === 'callable')
        .map((node) => node.stableKey)
        .sort(),
    )
  })
}

test('root chains compact, preserve wrapper relations and disconnected folders', () => {
  const artifact = tree([
    ['src', 'folder', null],
    ['src/main', 'folder', 'src'],
    ['src/main/java', 'folder', 'src/main'],
    ['src/main/java/A.java', 'file', 'src/main/java'],
    ['external', 'external', 'src'],
    ['isolated', 'folder', null],
    ['target', 'file', null],
  ])
  for (const source of [
    'src',
    'src/main',
    'src/main/java',
    'src/main/java/A.java',
  ])
    artifact.edges.push({
      sourceStableKey: source,
      targetStableKey: 'target',
      type: 'IMPORTS',
      confidence: 'EXTRACTED',
    })
  artifact.edges.push({
    sourceStableKey: 'target',
    targetStableKey: 'src/main',
    type: 'USES',
    confidence: 'EXTRACTED',
  })
  artifact.edges.push({
    sourceStableKey: 'src',
    targetStableKey: 'src/main',
    type: 'USES',
    confidence: 'EXTRACTED',
  })
  const before = structuredClone(artifact)
  const graph = buildProjectGraph(artifact, { kind: 'repository' })
  expect(ids(graph)).toEqual(['isolated', 'src/main/java', 'target'])
  expect(graph.nodes.find((node) => node.id === 'src/main/java')).toMatchObject(
    {
      label: 'src/main/java',
      path: 'src/main/java',
      detail: '1 file',
      scope: { kind: 'folder', key: 'src/main/java' },
    },
  )
  expect(graph.nodes.find((node) => node.id === 'isolated')?.detail).toBe(
    '0 files',
  )
  expectRelations({
    graph,
    source: 'src/main/java',
    target: 'target',
    relationships: { IMPORTS: 4 },
  })
  expectRelations({
    graph,
    source: 'target',
    target: 'src/main/java',
    relationships: { USES: 1 },
  })
  expectDirectProjection(artifact, graph)
  expect(artifact).toEqual(before)
})

test('folders with null paths are not synthetic transparent wrappers', () => {
  const artifact = tree([
    ['folder', 'folder', null],
    ['child', 'file', 'folder'],
  ])
  artifact.nodes[0].path = null
  expect(ids(buildProjectGraph(artifact, { kind: 'repository' }))).toEqual([
    'folder',
  ])
  expect(getGraphTrail(artifact, { kind: 'folder', key: 'folder' })).toEqual([
    { label: 'synthetic', scope: { kind: 'repository' } },
    { label: 'folder', scope: { kind: 'folder', key: 'folder' } },
  ])
})

test('compaction stops at files, branches, and other indexed children', () => {
  for (const kind of ['file', 'folder', 'symbol']) {
    const artifact = tree([
      ['a', 'folder', null],
      ['a/b', 'folder', 'a'],
      ['a/b/c', 'folder', 'a/b'],
      ['a/b/extra', kind, 'a/b'],
      ['a/b/c/file', 'file', 'a/b/c'],
    ])
    const graph = buildProjectGraph(artifact, { kind: 'repository' })
    expect(ids(graph)).toEqual(['a/b'])
    expect(graph.nodes[0].label).toBe('a/b')
    expect(graph.nodes[0].detail).toBe(kind === 'file' ? '2 files' : '1 file')
  }
})

test('trails retain actual compacted ancestors without repository or dot duplicates', () => {
  const artifact = fixture()
  expect(getGraphTrail(artifact, { kind: 'repository' })).toEqual([
    { label: 'synthetic', scope: { kind: 'repository' } },
  ])
  for (const key of ['java', 'com', 'acme', 'service']) {
    const chain = ['app', 'pkg', 'java', 'com', 'acme', 'service']
    const trail = getGraphTrail(artifact, {
      kind: key === 'service' ? 'file' : 'folder',
      key,
    })
    expect(trail).toEqual([
      { label: 'synthetic', scope: { kind: 'repository' } },
      ...chain.slice(0, chain.indexOf(key) + 1).map((label) => ({
        label,
        scope: {
          kind: label === 'service' ? 'file' : 'folder',
          key: label,
        } satisfies GraphScope,
      })),
    ])
    expectNavigableTrail(artifact, trail, buildProjectGraph)
  }
})

test('empty files are valid; external descendants and unknown kinds are invalid scopes', () => {
  const artifact = tree([
    ['empty', 'file', null],
    ['external', 'external', null],
    ['hidden', 'folder', 'external'],
    ['hidden-file', 'file', 'hidden'],
  ])
  expect(buildProjectGraph(artifact, { kind: 'file', key: 'empty' })).toEqual({
    nodes: [],
    edges: [],
  })
  for (const scope of [
    { kind: 'folder', key: 'hidden' },
    { kind: 'file', key: 'hidden-file' },
    { kind: 'invalid' } as unknown as GraphScope,
  ] satisfies Array<GraphScope>) {
    expect(() => buildProjectGraph(artifact, scope)).toThrow('scope')
    expect(() => getGraphTrail(artifact, scope)).toThrow('scope')
  }
})

test('deep branching folders remain navigable without a fixed level limit', () => {
  const rows: Array<[string, string, string | null]> = []
  for (let index = 0; index < 24; index++) {
    rows.push([`d${index}`, 'folder', index ? `d${index - 1}` : null])
    rows.push([`f${index}`, 'file', `d${index}`])
  }
  const artifact = tree(rows)
  for (let index = 0; index < 24; index++) {
    const scope: GraphScope = { kind: 'folder', key: `d${index}` }
    expect(ids(buildProjectGraph(artifact, scope))).toEqual(
      index === 23 ? ['f23'] : [`d${index + 1}`, `f${index}`].sort(),
    )
    expect(getGraphTrail(artifact, scope)).toHaveLength(index + 2)
  }
})
