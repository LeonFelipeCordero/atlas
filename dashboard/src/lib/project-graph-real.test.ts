import { beforeAll, expect, test } from 'bun:test'
import { importedArtifact } from './imported-artifact-fixture'
import { buildProjectGraph, ids } from './project-graph-test.helpers'
import type { GraphScope, ProjectGraph } from './project-graph'

// Cold Python/grammar startup belongs to fixture setup, not the five-second tests.
beforeAll(() => {
  importedArtifact()
}, 30_000)

test('CLI-imported Kotlin class methods render in file scope', () => {
  const artifact = importedArtifact()
  const file = artifact.nodes.find(
    (node) => node.level === 'file' && node.path?.endsWith('/ChannelApi.kt'),
  )!
  const owner = artifact.nodes.find(
    (node) => node.name === 'ChannelApi' && node.path === file.path,
  )!
  const graph = buildProjectGraph(artifact, {
    kind: 'file',
    key: file.stableKey,
  })
  expect(graph.nodes.map((node) => node.label).sort()).toEqual([
    'addRoutingKey',
    'createChannel',
    'deleteChannel',
    'findByName',
  ])
  for (const node of graph.nodes) {
    expect(node.kind).toBe('function')
    expect(
      artifact.nodes.find((entry) => entry.stableKey === node.id)
        ?.parentStableKey,
    ).toBe(owner.stableKey)
  }
})

test('imported package scopes expose immediate folders; language modules never become folder nodes', () => {
  const artifact = importedArtifact()
  const packages = buildProjectGraph(artifact, {
    kind: 'folder',
    key: 'module:extensions',
  })
  expect(ids(packages)).toEqual([
    'module:extensions/service',
    'module:extensions/tools',
  ])
  expect(ids(packages)).toEqual(
    artifact.nodes
      .filter(
        (node) =>
          node.parentStableKey === 'module:extensions' &&
          ['directory', 'file'].includes(node.kind),
      )
      .map((node) => node.stableKey)
      .sort(),
  )
  const elixir = artifact.nodes.find(
    (node) => node.level === 'file' && node.path?.endsWith('application.ex'),
  )!
  const functions = buildProjectGraph(artifact, {
    kind: 'file',
    key: elixir.stableKey,
  })
  expect(functions.nodes.map((node) => node.label).sort()).toEqual([
    'initialize',
    'start',
  ])
  expect(functions.nodes.every((node) => node.kind === 'function')).toBe(true)
  const files: ProjectGraph = { nodes: [], edges: [] }
  const pending: Array<GraphScope> = [
    { kind: 'folder', key: 'module:src/main' },
  ]
  for (const scope of pending) {
    const graph = buildProjectGraph(artifact, scope)
    files.nodes.push(...graph.nodes.filter((node) => node.kind === 'file'))
    pending.push(
      ...graph.nodes.flatMap((node) =>
        node.scope?.kind === 'folder' ? [node.scope] : [],
      ),
    )
  }
  expect(ids(files)).toEqual(
    artifact.nodes
      .filter(
        (node) =>
          node.level === 'file' &&
          node.ancestorStableKeys.includes('module:src/main'),
      )
      .map((node) => node.stableKey)
      .sort(),
  )
  expect(files.nodes).toHaveLength(2)
  expect(files.nodes.some((node) => node.path.endsWith('ChannelApi.kt'))).toBe(
    true,
  )
  expect(files.nodes.every((node) => node.kind === 'file')).toBe(true)
})
