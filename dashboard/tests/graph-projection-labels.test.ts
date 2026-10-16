import { expect, test } from 'bun:test'
import { buildProjectGraph } from '../src/lib/project-graph'
import type { ArtifactNode } from '../src/lib/architecture-artifact'

function node(
  key: string,
  parent: string | null = null,
  level = 'file',
): ArtifactNode {
  return {
    stableKey: key,
    name: key,
    path: key,
    type: level === 'callable' ? 'function' : level,
    kind: level === 'callable' ? 'function' : level,
    level,
    parentStableKey: parent,
    ancestorStableKeys: parent ? [parent] : [],
    depth: parent ? 1 : 0,
    language: null,
  }
}

test('graph labels fall back from name to qualified name and stable key', () => {
  const first = { ...node('first'), name: '', qualifiedName: 'qualified.First' }
  const second = { ...node('second'), name: '', qualifiedName: '' }
  const third = { ...node('third'), qualifiedName: 'qualified.Third' }
  const graph = buildProjectGraph(
    { nodes: [first, second, third], edges: [] },
    { kind: 'repository' },
  )
  expect(graph.nodes.map((item) => item.label)).toEqual([
    'qualified.First',
    'second',
    'third',
  ])
})

test('callable details retain missing, single-line and multiline source ranges', () => {
  const file = node('file')
  const bare = node('bare', 'file', 'callable')
  const one = { ...node('one', 'file', 'callable'), startLine: 5, endLine: 5 }
  const many = { ...node('many', 'file', 'callable'), startLine: 6, endLine: 9 }
  const start = { ...node('start', 'file', 'callable'), startLine: 10 }
  const graph = buildProjectGraph(
    { nodes: [file, bare, one, many, start], edges: [] },
    { kind: 'file', key: 'file' },
  )
  expect(graph.nodes.map((item) => item.detail)).toEqual([
    'function · bare',
    'function · one:5',
    'function · many:6–9',
    'function · start:10',
  ])
})

test('compacted folder labels use path segments rather than display names', () => {
  const outer = {
    ...node('outer'),
    type: 'directory',
    kind: 'directory',
    level: 'folder',
    path: 'src',
    name: 'Outer label',
  }
  const inner = {
    ...node('inner', 'outer'),
    type: 'directory',
    kind: 'directory',
    level: 'folder',
    path: 'src/lib',
    name: 'Inner label',
  }
  const file = {
    ...node('file', 'inner'),
    ancestorStableKeys: ['outer', 'inner'],
    depth: 2,
  }
  const graph = buildProjectGraph(
    { nodes: [outer, inner, file], edges: [] },
    { kind: 'repository' },
  )
  expect(graph.nodes).toHaveLength(1)
  expect(graph.nodes[0].id).toBe('inner')
  expect(graph.nodes[0].label).toBe('src/lib')
})

test('external level and external type independently prevent root navigation', () => {
  const byType = { ...node('by-type'), type: 'external' }
  const byLevel = { ...node('by-level'), level: 'external' }
  expect(
    buildProjectGraph(
      { nodes: [byType, byLevel], edges: [] },
      { kind: 'repository' },
    ),
  ).toEqual({ nodes: [], edges: [] })
})
