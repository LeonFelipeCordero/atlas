import { expect, test } from 'bun:test'
import {
  containingCycleScope,
  cycleContainsNode,
  projectCycles,
} from '../src/lib/graph-cycles'
import type {
  ArtifactNode,
  CircularDependency,
} from '../src/lib/architecture-artifact'
import type { GraphNode } from '../src/lib/project-graph'

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
    level: kind === 'directory' ? 'folder' : kind,
    parentStableKey: ancestors.at(-1) ?? null,
    ancestorStableKeys: ancestors,
    language: null,
    depth: ancestors.length,
  }
}
const group: CircularDependency = {
  id: 'cycle',
  nodeStableKeys: ['a', 'b'],
  exampleCycle: ['a', 'b', 'a'],
  edges: [
    {
      sourceStableKey: 'a',
      targetStableKey: 'b',
      type: 'IMPORTS',
      confidence: 'EXTRACTED',
    },
  ],
}

function graphNode(id: string, kind: GraphNode['kind'] = 'file'): GraphNode {
  return { id, kind, label: id, path: id, detail: '', scope: null }
}

test('common cycle scope rejects synthetic paths and nonfolder ancestors', () => {
  for (const [kind, path] of [
    ['directory', '.'],
    ['directory', ''],
    ['module', 'src'],
  ]) {
    const artifact = {
      nodes: [
        { ...node('wrapper', [], kind), path },
        node('unrelated', [], 'directory'),
        node('a', ['wrapper']),
        node('b', ['wrapper']),
      ],
    }
    expect(containingCycleScope(artifact, group)).toEqual({
      kind: 'repository',
    })
  }
  const artifact = {
    nodes: [
      node('other', [], 'directory'),
      node('src', [], 'directory'),
      node('a', ['src']),
      node('b', ['src']),
    ],
  }
  expect(containingCycleScope(artifact, group)).toEqual({
    kind: 'folder',
    key: 'src',
  })
})

test('folders contain cycles only through actual member descendants', () => {
  const artifact = {
    nodes: [
      node('src', [], 'directory'),
      node('a', ['src']),
      node('b', []),
      node('unrelated', ['elsewhere']),
    ],
  }
  expect(cycleContainsNode(artifact, group, graphNode('src', 'folder'))).toBe(
    true,
  )
  expect(
    cycleContainsNode(artifact, group, graphNode('elsewhere', 'folder')),
  ).toBe(false)
})

test('cycle projection excludes missing edge endpoints and scopes with no member', () => {
  const artifact = {
    nodes: [node('a', []), node('b', [])],
    edges: group.edges,
    circularDependencies: { version: 1 as const, groups: [group] },
  }
  const projected = projectCycles(
    artifact,
    { nodes: [graphNode('b')], edges: [] },
    { kind: 'repository' },
  )!
  expect(projected).toHaveLength(1)
  expect(projected[0].edges).toEqual([])
  expect(
    projectCycles(
      artifact,
      { nodes: [], edges: [] },
      { kind: 'folder', key: 'unrelated' },
    ),
  ).toEqual([])
  expect(
    projectCycles(
      artifact,
      { nodes: [graphNode('a')], edges: [] },
      { kind: 'folder', key: 'unrelated' },
    ),
  ).toHaveLength(1)
  artifact.nodes.push(
    node('c', []),
    node('fn', ['c'], 'function'),
    node('member-fn', ['a'], 'function'),
  )
  expect(
    projectCycles(
      artifact,
      { nodes: [graphNode('member-fn', 'function')], edges: [] },
      { kind: 'file', key: 'c' },
    ),
  ).toHaveLength(1)
  expect(
    projectCycles(
      artifact,
      { nodes: [graphNode('fn', 'function')], edges: [] },
      { kind: 'file', key: 'c' },
    ),
  ).toEqual([])
})
