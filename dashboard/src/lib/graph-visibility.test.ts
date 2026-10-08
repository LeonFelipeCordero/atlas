import { expect, test } from 'bun:test'
import { hideTestFiles, isTestPath } from './graph-visibility'
import { buildProjectGraph } from './project-graph'
import type { Artifact, ArtifactNode } from './architecture-artifact'

for (const path of [
  'src/widget.test.tsx',
  'packages/web/widget.spec.ts',
  'test/widget_test.exs',
  'apps/api/test/support/helper.ex',
  'module/src/test/java/App.java',
  'module/src/integrationTest/kotlin/App.kt',
  'src/__tests__/helper.ts',
  'tests/helpers.py',
  'src/test_widget.py',
  'src/widget_test.py',
  'pkg/widget_test.go',
  'spec/widget_spec.rb',
  'src/AppTest.java',
  'module/src/androidTest/App.kt',
  '.\\packages\\web\\widget.test.ts',
])
  test(`detects ${path}`, () => expect(isTestPath(path)).toBe(true))

for (const path of [
  'src/contest.ts',
  'src/testimonials.ts',
  'src/spec.tsx',
  'src/Test.java',
  'src/test.ts',
  'src/widget.ts',
])
  test(`retains ${path}`, () => expect(isTestPath(path)).toBe(false))

test('detects test directories without confusing directory names with filenames', () => {
  expect(isTestPath('packages/api/test', true)).toBe(true)
  expect(isTestPath('src/widget.test.ts', true)).toBe(false)
  expect(isTestPath('src/testing', true)).toBe(false)
})

function node(
  key: string,
  parent: string | null,
  path: string | null,
  level = 'file',
): ArtifactNode {
  return {
    stableKey: key,
    parentStableKey: parent,
    path,
    level,
    type: level,
    kind: level === 'folder' ? 'directory' : level,
    name: key,
    language: null,
    depth: parent ? 1 : 0,
    ancestorStableKeys: parent ? [parent] : [],
  }
}

function fixture(): Artifact {
  return {
    schemaVersion: 2,
    repository: { name: 'sample' },
    nodes: [
      node('testFn', 'testFile', null, 'callable'),
      node('testFile', 'src', 'src/widget.test.ts'),
      node('helper', 'tests', 'tests/helper.ts'),
      node('tests', null, 'tests', 'folder'),
      node('fn', 'file', null, 'callable'),
      node('file', 'src', 'src/widget.ts'),
      node('src', null, 'src', 'folder'),
      node('libFile', 'lib', 'lib/util.ts'),
      node('lib', null, 'lib', 'folder'),
      node('empty', null, 'empty', 'folder'),
    ],
    edges: [
      {
        sourceStableKey: 'testFn',
        targetStableKey: 'libFile',
        type: 'CALLS',
        confidence: 'EXTRACTED',
      },
      {
        sourceStableKey: 'fn',
        targetStableKey: 'libFile',
        type: 'CALLS',
        confidence: 'EXTRACTED',
      },
      {
        sourceStableKey: 'fn',
        targetStableKey: 'testFn',
        type: 'CALLS',
        confidence: 'EXTRACTED',
      },
    ],
  }
}

test('hides tests, descendants, and their edges without changing the imported artifact', () => {
  const artifact = fixture()
  const before = JSON.stringify(artifact)
  const visible = hideTestFiles(artifact)
  expect(visible.nodes.map((entry) => entry.stableKey)).toEqual([
    'fn',
    'file',
    'src',
    'libFile',
    'lib',
    'empty',
  ])
  expect(visible.edges).toEqual([artifact.edges[1]])
  expect(JSON.stringify(artifact)).toBe(before)
  const graph = buildProjectGraph(visible, { kind: 'repository' })
  expect(graph.edges[0]?.count).toBe(1)
  expect(graph.nodes.find((entry) => entry.id === 'src')?.detail).toBe('1 file')
  expect(
    buildProjectGraph(artifact, { kind: 'repository' }).edges[0]?.count,
  ).toBe(2)
  expect(
    buildProjectGraph(visible, { kind: 'folder', key: 'src' }).nodes.map(
      (entry) => entry.id,
    ),
  ).toEqual(['file', 'lib'])
})

test('prunes newly empty test folders but preserves unrelated empty folders', () => {
  const artifact = fixture()
  artifact.nodes.push(
    node('only', null, 'only', 'folder'),
    node('nested', 'only', 'only/nested', 'folder'),
    node('spec', 'nested', 'only/nested/foo.spec.ts'),
  )
  const visible = hideTestFiles(artifact)
  expect(
    visible.nodes.some((entry) =>
      ['only', 'nested', 'spec'].includes(entry.stableKey),
    ),
  ).toBe(false)
  expect(visible.nodes.some((entry) => entry.stableKey === 'empty')).toBe(true)
  expect(
    hideTestFiles({
      schemaVersion: 2,
      repository: { name: 'empty' },
      nodes: [],
      edges: [],
    }).nodes,
  ).toEqual([])
})
