import { expect, test } from 'bun:test'
import { addBoundaryDependencies } from '../src/lib/project-graph-boundary'
import type { ArtifactNode } from '../src/lib/architecture-artifact'
import type { GraphNode } from '../src/lib/project-graph'

function node(key: string, type: string, level: string): ArtifactNode {
  return {
    stableKey: key,
    name: key,
    path: key,
    kind: type,
    type,
    level,
    parentStableKey: null,
    ancestorStableKeys: [],
    depth: 0,
    language: null,
  }
}

test('external type and external level independently exclude dependency boundaries', () => {
  for (const [type, level] of [
    ['external', 'callable'],
    ['function', 'external'],
  ]) {
    const source = node('source', 'file', 'file')
    const external = node('external', type, level)
    const target = {
      ...node('target', 'function', 'callable'),
      parentStableKey: 'external',
      ancestorStableKeys: ['external'],
    }
    const nodes: Array<GraphNode> = []
    const result = addBoundaryDependencies({
      artifact: {
        nodes: [source, external, target],
        edges: [
          {
            sourceStableKey: 'source',
            targetStableKey: 'target',
            type: 'CALLS',
            confidence: 'EXTRACTED',
          },
        ],
      },
      scope: { kind: 'file', key: 'source' },
      local: new Map([['source', 'source']]),
      nodes,
      render: () => ({
        id: 'target',
        label: 'Target',
        path: 'target',
        kind: 'function',
        detail: '',
        scope: null,
      }),
    })
    expect([...result]).toEqual([['source', 'source']])
    expect(nodes).toEqual([])
  }
})
