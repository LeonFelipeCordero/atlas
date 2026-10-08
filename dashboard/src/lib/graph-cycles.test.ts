import { expect, test } from 'bun:test'
import {
  containingCycleScope,
  cycleContainsNode,
  projectCycles,
} from './graph-cycles'
import { buildProjectGraph } from './project-graph'
import type {
  Artifact,
  ArtifactNode,
  CircularDependency,
} from './architecture-artifact'

function node(
  key: string,
  ancestors: Array<string>,
  kind = 'file',
): ArtifactNode {
  return {
    stableKey: key,
    name: key,
    path: key,
    type: kind,
    kind,
    level:
      kind === 'directory' ? 'folder' : kind === 'function' ? 'callable' : kind,
    parentStableKey: ancestors.at(-1) ?? null,
    ancestorStableKeys: ancestors,
    language: null,
    depth: ancestors.length,
  }
}
function fixture(): Artifact {
  const edges = [
    ['src/a', 'lib/b'],
    ['lib/b', 'src/a'],
  ].map(([sourceStableKey, targetStableKey]) => ({
    sourceStableKey,
    targetStableKey,
    type: 'IMPORTS',
    confidence: 'EXTRACTED' as const,
  }))
  return {
    schemaVersion: 2,
    repository: { name: 'sample' },
    edges,
    nodes: [
      node('src', [], 'directory'),
      node('lib', [], 'directory'),
      node('src/a', ['src']),
      node('lib/b', ['lib']),
      node('fn', ['src', 'src/a'], 'function'),
    ],
    circularDependencies: {
      version: 1,
      groups: [
        {
          id: 'cycle',
          nodeStableKeys: ['src/a', 'lib/b'],
          exampleCycle: ['src/a', 'lib/b', 'src/a'],
          edges: [...edges],
        },
      ],
    },
  }
}
const group = (artifact: Artifact): CircularDependency =>
  artifact.circularDependencies!.groups[0]

test('projects exported member files into collapsed folders and actual directed imports', () => {
  const artifact = fixture()
  const graph = buildProjectGraph(artifact, { kind: 'repository' })
  const [cycle] = projectCycles(artifact, graph, { kind: 'repository' })!
  expect(cycle.nodeIds).toEqual(['src', 'lib'])
  expect(cycle.edges.map((edge) => [edge.source, edge.target])).toEqual([
    ['src', 'lib'],
    ['lib', 'src'],
  ])
  expect(cycle.outsideCount).toBe(0)
  expect(cycle.scope).toEqual({ kind: 'repository' })
})

test('partial views include boundaries but count members outside the current scope', () => {
  const artifact = fixture()
  const scope = { kind: 'folder' as const, key: 'src' }
  const [cycle] = projectCycles(
    artifact,
    buildProjectGraph(artifact, scope),
    scope,
  )!
  expect(cycle.outsideCount).toBe(1)
  expect(cycle.nodeIds).toContain('src/a')
  const partial = projectCycles(artifact, { nodes: [], edges: [] }, scope)![0]
  expect(partial.edges).toEqual([])
  expect(partial.scope).toEqual({ kind: 'repository' })
})

test('function selection links its owning file without projecting imports onto functions', () => {
  const artifact = fixture()
  const scope = { kind: 'file' as const, key: 'src/a' }
  const graph = buildProjectGraph(artifact, scope)
  expect(cycleContainsNode(artifact, group(artifact), graph.nodes[0])).toBe(
    true,
  )
  const [cycle] = projectCycles(artifact, graph, scope)!
  expect(cycle.nodeIds).not.toContain('fn')
  expect(cycle.edges).toEqual([])
  const root = buildProjectGraph(artifact, { kind: 'repository' })
  expect(cycleContainsNode(artifact, group(artifact), root.nodes[0])).toBe(true)
})

test('nearest shared folder contains the full group, even for self imports', () => {
  const artifact = fixture()
  const self = {
    ...group(artifact),
    nodeStableKeys: ['src/a'],
    exampleCycle: ['src/a', 'src/a'],
  }
  expect(containingCycleScope(artifact, self)).toEqual({
    kind: 'folder',
    key: 'src',
  })
})

test('hidden test members remove the whole group without inventing a smaller cycle', () => {
  const artifact = fixture()
  artifact.nodes.find((item) => item.stableKey === 'lib/b')!.path =
    'lib/b.test.ts'
  expect(
    projectCycles(
      artifact,
      buildProjectGraph(artifact, { kind: 'repository' }),
      { kind: 'repository' },
    ),
  ).toEqual([])
})

test('collapsed internal imports do not invent folder self edges; direct self imports remain', () => {
  const artifact = fixture()
  const member = artifact.nodes.find((item) => item.stableKey === 'lib/b')!
  member.parentStableKey = 'src'
  member.ancestorStableKeys = ['src']
  const scope = { kind: 'repository' as const }
  const [collapsed] = projectCycles(
    artifact,
    buildProjectGraph(artifact, scope),
    scope,
  )!
  expect(collapsed.nodeIds).toEqual(['src'])
  expect(collapsed.edges).toEqual([])
  expect(collapsed.scope).toEqual({ kind: 'folder', key: 'src' })
  const cycle = group(artifact)
  cycle.nodeStableKeys = ['src/a']
  cycle.exampleCycle = ['src/a', 'src/a']
  cycle.edges = [{ ...cycle.edges[0], targetStableKey: 'src/a' }]
  const folder = { kind: 'folder' as const, key: 'src' }
  const [self] = projectCycles(
    artifact,
    buildProjectGraph(artifact, folder),
    folder,
  )!
  expect(self.edges.map((edge) => [edge.source, edge.target])).toEqual([
    ['src/a', 'src/a'],
  ])
})

test('selection edges come from the export, not unrelated relationships among members', () => {
  const artifact = fixture()
  artifact.edges.push({
    sourceStableKey: 'src/a',
    targetStableKey: 'src/a',
    type: 'CALLS',
    confidence: 'EXTRACTED',
  })
  const scope = { kind: 'folder' as const, key: 'src' }
  const [cycle] = projectCycles(
    artifact,
    buildProjectGraph(artifact, scope),
    scope,
  )!
  expect(cycle.edges).toHaveLength(2)
  expect(cycle.edges.every((edge) => edge.source !== edge.target)).toBe(true)
})

test('legacy unavailable differs from analyzed zero and no TS detection occurs', () => {
  const artifact = fixture()
  const graph = buildProjectGraph(artifact, { kind: 'repository' })
  delete artifact.circularDependencies
  expect(projectCycles(artifact, graph, { kind: 'repository' })).toBeUndefined()
  artifact.circularDependencies = { version: 1, groups: [] }
  expect(projectCycles(artifact, graph, { kind: 'repository' })).toEqual([])
})
